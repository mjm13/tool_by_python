"""
网易云音乐VIP歌曲管理工具 - 主程序
自动扫描"我喜欢的音乐"，将VIP歌曲添加到指定歌单并取消喜欢
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .auth import NeteaseAuth
from .music_scanner import MusicScanner
from .playlist_manager import PlaylistManager
from .utils import setup_logger, load_config, confirm_action, format_song_info

console = Console()
logger: Optional[logging.Logger] = None


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="网易云音乐VIP歌曲管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置运行
  python -m netease_vip_manager.main
  
  # 仅预览，不执行实际操作
  python -m netease_vip_manager.main --dry-run
  
  # 指定VIP歌单名称
  python -m netease_vip_manager.main --playlist-name "我的VIP歌曲"
  
  # 使用手机号登录
  python -m netease_vip_manager.main --login-method phone
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.ini',
        help='配置文件路径 (默认: config.ini)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅预览操作，不实际执行'
    )
    
    parser.add_argument(
        '--login-method',
        type=str,
        choices=['qr_code', 'phone'],
        help='登录方式 (qr_code=二维码, phone=手机号)'
    )
    
    parser.add_argument(
        '--playlist-id',
        type=int,
        help='VIP歌单ID（留空则自动创建）'
    )
    
    parser.add_argument(
        '--playlist-name',
        type=str,
        help='VIP歌单名称（自动创建时使用）'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='跳过确认提示，直接执行'
    )
    
    return parser.parse_args()


def load_settings(args):
    """加载设置（合并配置文件和命令行参数）"""
    config = load_config(args.config)
    
    settings = {
        'login_method': args.login_method or config.get('auth', 'login_method', fallback='qr_code'),
        'playlist_id': args.playlist_id or config.get('settings', 'vip_playlist_id', fallback='0'),
        'playlist_name': args.playlist_name or config.get('settings', 'vip_playlist_name', fallback='VIP专属歌曲'),
        'dry_run': args.dry_run or config.getboolean('settings', 'dry_run', fallback=False),
        'request_delay': config.getfloat('settings', 'request_delay', fallback=0.5),
        'log_level': args.log_level or config.get('logging', 'log_level', fallback='INFO'),
        'save_log': config.getboolean('logging', 'save_to_file', fallback=True),
        'no_confirm': args.no_confirm,
    }
    
    return settings


def display_banner():
    """显示欢迎横幅"""
    banner_text = """
[bold cyan]网易云音乐VIP歌曲管理工具[/bold cyan]
[dim]自动管理VIP专属歌曲[/dim]
    """
    
    panel = Panel(
        banner_text.strip(),
        border_style="cyan",
        padding=(1, 2)
    )
    
    console.print()
    console.print(panel)
    console.print()


def display_summary(vip_count: int, add_result: dict, unlike_result: dict):
    """显示操作总结"""
    table = Table(
        title="操作总结",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan"
    )
    
    table.add_column("项目", style="bold")
    table.add_column("数量", justify="right", style="green")
    
    table.add_row("发现VIP歌曲", str(vip_count))
    table.add_row("成功添加到歌单", str(add_result.get('success', 0)))
    table.add_row("成功取消喜欢", str(unlike_result.get('success', 0)))
    
    if add_result.get('failed', 0) > 0:
        table.add_row("添加失败", str(add_result['failed']), style="red")
    
    if unlike_result.get('failed', 0) > 0:
        table.add_row("取消喜欢失败", str(unlike_result['failed']), style="red")
    
    console.print()
    console.print(table)
    console.print()


def main():
    """主程序入口"""
    global logger
    
    # 解析参数
    args = parse_arguments()
    settings = load_settings(args)
    
    # 初始化日志
    logger = setup_logger(settings['log_level'], settings['save_log'])
    
    try:
        # 显示欢迎信息
        display_banner()
        
        if settings['dry_run']:
            console.print("[yellow]⚠ DRY-RUN 模式：将仅预览操作，不执行实际修改[/yellow]\n")
        
        # 步骤1: 登录
        console.print("[bold cyan]步骤 1/4: 登录网易云音乐[/bold cyan]")
        auth = NeteaseAuth()
        
        if not auth.login(method=settings['login_method']):
            console.print("[red]✗ 登录失败，程序退出[/red]")
            return 1
        
        user_id = auth.get_user_id()
        if not user_id:
            console.print("[red]✗ 无法获取用户ID，程序退出[/red]")
            return 1
        
        # 步骤2: 扫描VIP歌曲
        console.print("\n[bold cyan]步骤 2/4: 扫描VIP歌曲[/bold cyan]")
        scanner = MusicScanner(user_id)
        vip_songs = scanner.scan()
        
        if not vip_songs:
            console.print("[green]✓ 没有发现VIP歌曲，无需处理[/green]")
            return 0
        
        # 显示VIP歌曲（最多20首）
        scanner.display_vip_songs(limit=20)
        
        # 获取歌曲ID列表
        vip_song_ids = scanner.get_vip_song_ids()
        
        # 步骤3: 确认操作
        console.print("\n[bold cyan]步骤 3/4: 确认操作[/bold cyan]")
        
        if settings['dry_run']:
            console.print("[yellow]DRY-RUN 模式已启用，跳过实际操作[/yellow]")
            console.print(f"[dim]将会添加 {len(vip_song_ids)} 首歌曲到VIP歌单[/dim]")
            console.print(f"[dim]将会取消 {len(vip_song_ids)} 首歌曲的喜欢标记[/dim]")
            return 0
        
        if not settings['no_confirm']:
            console.print("[yellow]即将执行以下操作:[/yellow]")
            console.print(f"  1. 添加 {len(vip_song_ids)} 首歌曲到VIP歌单")
            console.print(f"  2. 取消 {len(vip_song_ids)} 首歌曲的喜欢标记")
            console.print()
            
            if not confirm_action("是否继续？", default=False):
                console.print("[yellow]操作已取消[/yellow]")
                return 0
        
        # 步骤4: 执行操作
        console.print("\n[bold cyan]步骤 4/4: 执行操作[/bold cyan]")
        
        playlist_manager = PlaylistManager(user_id)
        
        # 4.1: 获取或创建VIP歌单
        if settings['playlist_id']:
            vip_playlist_id = settings['playlist_id']
            console.print(f"[cyan]使用指定的VIP歌单 ID: {vip_playlist_id}[/cyan]")
        else:
            vip_playlist_id = playlist_manager.get_or_create_playlist(settings['playlist_name'])
        
        # 4.2: 添加歌曲到歌单
        add_result = playlist_manager.add_songs_incrementally(
            vip_playlist_id,
            vip_song_ids,
            delay=settings['request_delay']
        )
        
        # 4.3: 取消喜欢
        unlike_result = playlist_manager.unlike_songs(
            vip_song_ids,
            delay=settings['request_delay']
        )
        
        # 显示总结
        display_summary(len(vip_songs), add_result, unlike_result)
        
        # 检查是否有失败的操作
        if add_result.get('failed', 0) > 0 or unlike_result.get('failed', 0) > 0:
            console.print("[yellow]⚠ 部分操作失败，请查看日志了解详情[/yellow]")
            
            # 保存失败的歌曲ID
            failed_ids = set(add_result.get('failed_ids', []) + unlike_result.get('failed_ids', []))
            if failed_ids:
                failed_file = Path("failed_songs.txt")
                with open(failed_file, 'w', encoding='utf-8') as f:
                    for song_id in failed_ids:
                        f.write(f"{song_id}\n")
                console.print(f"[dim]失败的歌曲ID已保存到: {failed_file}[/dim]")
        else:
            console.print("[green]✓ 所有操作成功完成！[/green]")
        
        return 0
    
    except KeyboardInterrupt:
        console.print("\n[yellow]程序被用户中断[/yellow]")
        return 130
    
    except Exception as e:
        logger.exception("程序运行出错")
        console.print(f"\n[red]✗ 错误: {str(e)}[/red]")
        return 1


if __name__ == '__main__':
    sys.exit(main())
