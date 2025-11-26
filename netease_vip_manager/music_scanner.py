"""
音乐扫描模块
扫描"我喜欢的音乐"并识别VIP歌曲
"""

import logging
from typing import List, Dict, Any
from pyncm import apis
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from .utils import retry_on_error

console = Console()
logger = logging.getLogger("netease_vip_manager")


class MusicScanner:
    """音乐扫描器"""
    
    # VIP歌曲的fee类型
    VIP_FEE_TYPES = [1, 8]  # 1=VIP专属, 8=VIP高音质
    
    def __init__(self, user_id: int):
        """
        初始化音乐扫描器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.liked_songs: List[Dict[str, Any]] = []
        self.vip_songs: List[Dict[str, Any]] = []
    
    @retry_on_error(max_retries=3)
    def get_liked_playlist_id(self) -> int:
        """
        获取"我喜欢的音乐"歌单ID
        
        Returns:
            歌单ID
        """
        logger.info("正在获取用户歌单...")
        
        result = apis.user.GetUserPlaylists(self.user_id, limit=1000)
        
        if result.get('code') != 200:
            raise Exception(f"获取歌单失败: {result}")
        
        playlists = result.get('playlist', [])
        
        # "我喜欢的音乐"通常是第一个歌单，且名称包含"喜欢"
        for playlist in playlists:
            # 检查是否是用户自己的歌单（创建者是自己）
            if playlist.get('userId') == self.user_id:
                # 检查特殊类型标记或者名称
                if playlist.get('specialType') == 5:  # 5表示"我喜欢的音乐"
                    return playlist['id']
                # 备用检查：名称包含"喜欢"
                if '喜欢' in playlist.get('name', ''):
                    return playlist['id']
        
        raise Exception("未找到'我喜欢的音乐'歌单")
    
    @retry_on_error(max_retries=3)
    def fetch_liked_songs(self) -> List[Dict[str, Any]]:
        """
        获取"我喜欢的音乐"中的所有歌曲
        
        Returns:
            歌曲列表
        """
        console.print("\n[cyan]═══ 扫描我喜欢的音乐 ═══[/cyan]\n")
        
        try:
            # 获取歌单ID
            playlist_id = self.get_liked_playlist_id()
            logger.info(f"找到'我喜欢的音乐'歌单 ID: {playlist_id}")
            
            # 获取歌单详情（包含所有歌曲）
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]正在获取歌曲列表...", total=None)
                
                result = apis.playlist.GetPlaylistAllTracks(playlist_id)
                
                if result.get('code') != 200:
                    raise Exception(f"获取歌曲列表失败: {result}")
                
                songs = result.get('songs', [])
                self.liked_songs = songs
                
                progress.update(task, completed=True, description=f"[green]✓ 获取到 {len(songs)} 首歌曲")
            
            logger.info(f"成功获取 {len(self.liked_songs)} 首歌曲")
            return self.liked_songs
        
        except Exception as e:
            logger.error(f"获取我喜欢的音乐失败: {e}")
            raise
    
    def identify_vip_songs(self) -> List[Dict[str, Any]]:
        """
        识别VIP歌曲
        
        Returns:
            VIP歌曲列表
        """
        if not self.liked_songs:
            logger.warning("还没有获取歌曲列表")
            return []
        
        console.print("[cyan]正在分析歌曲付费类型...[/cyan]")
        
        vip_songs = []
        
        # 调试：打印前几首歌的fee信息
        logger.debug("前5首歌曲的fee信息：")
        for i, song in enumerate(self.liked_songs[:5]):
            logger.debug(f"  {i+1}. {song.get('name', 'N/A')} - fee: {song.get('fee', 0)}, privilege: {song.get('privilege', {})}")
        
        for song in self.liked_songs:
            fee = song.get('fee', 0)
            privilege = song.get('privilege', {})
            
            # 检查是否是VIP歌曲
            # fee = 1: VIP专属歌曲（需要VIP才能播放）
            # fee = 8: VIP高音质（普通音质免费，高音质需要VIP）
            # fee = 4: 购买专辑/单曲
            # fee = 0: 免费歌曲
            
            # 只有fee为1时才是真正的VIP专属歌曲
            # fee为8的歌曲可以免费听低音质，不应该移除
            if fee == 1:
                vip_songs.append(song)
                logger.debug(f"识别为VIP歌曲: {song.get('name', 'N/A')} (fee={fee}, privilege={privilege})")
        
        self.vip_songs = vip_songs
        
        console.print(f"[green]✓ 识别出 {len(vip_songs)} 首VIP专属歌曲[/green]\n")
        logger.info(f"识别出 {len(vip_songs)} 首VIP专属歌曲（fee=1）")
        
        return vip_songs
    
    def display_vip_songs(self, limit: int = 20) -> None:
        """
        显示VIP歌曲列表
        
        Args:
            limit: 最多显示的歌曲数量（0表示全部显示）
        """
        if not self.vip_songs:
            console.print("[yellow]没有发现VIP歌曲[/yellow]")
            return
        
        table = Table(
            title=f"VIP歌曲清单 (共 {len(self.vip_songs)} 首)",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan"
        )
        
        table.add_column("序号", style="dim", width=4)
        table.add_column("歌名", style="bold")
        table.add_column("歌手", style="green")
        table.add_column("专辑", style="dim")
        table.add_column("类型", style="yellow")
        
        display_songs = self.vip_songs[:limit] if limit > 0 else self.vip_songs
        
        for idx, song in enumerate(display_songs, 1):
            name = song.get('name', '未知歌曲')
            artists = ', '.join([ar.get('name', '') for ar in song.get('ar', [])])
            album = song.get('al', {}).get('name', '未知专辑')
            
            fee = song.get('fee', 0)
            fee_text = {
                1: 'VIP专属',
            }.get(fee, f'未知({fee})')
            
            table.add_row(
                str(idx),
                name,
                artists,
                album,
                fee_text
            )
        
        console.print(table)
        
        if limit > 0 and len(self.vip_songs) > limit:
            console.print(f"[dim]... 还有 {len(self.vip_songs) - limit} 首未显示[/dim]\n")
    
    def get_vip_song_ids(self) -> List[int]:
        """
        获取VIP歌曲的ID列表
        
        Returns:
            歌曲ID列表
        """
        return [song['id'] for song in self.vip_songs if 'id' in song]
    
    def scan(self) -> List[Dict[str, Any]]:
        """
        执行完整扫描流程
        
        Returns:
            VIP歌曲列表
        """
        # 1. 获取我喜欢的音乐
        self.fetch_liked_songs()
        
        # 2. 识别VIP歌曲
        self.identify_vip_songs()
        
        # 3. 显示结果
        self.display_vip_songs()
        
        return self.vip_songs
