"""
辅助工具函数模块
"""

import logging
import time
import json
from pathlib import Path
from typing import Any, Callable
from functools import wraps
from rich.console import Console
from rich.logging import RichHandler
from configparser import ConfigParser

console = Console()


def setup_logger(level: str = "INFO", save_to_file: bool = True) -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        save_to_file: 是否保存日志到文件
    
    Returns:
        配置好的logger实例
    """
    logger = logging.getLogger("netease_vip_manager")
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有handlers
    logger.handlers.clear()
    
    # 添加Rich终端handler
    logger.addHandler(RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=False,
        show_path=False
    ))
    
    # 可选：添加文件handler
    if save_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_dir / f"netease_vip_{time.strftime('%Y%m%d_%H%M%S')}.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(file_handler)
    
    return logger


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    错误重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟时间倍增因子
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            _delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger = logging.getLogger("netease_vip_manager")
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
                        )
                        logger.info(f"等待 {_delay:.1f} 秒后重试...")
                        time.sleep(_delay)
                        _delay *= backoff
                    else:
                        logger.error(f"{func.__name__} 重试 {max_retries} 次后仍然失败")
            
            raise last_exception
        
        return wrapper
    return decorator


def load_config(config_path: str = "config.ini") -> ConfigParser:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        ConfigParser实例
    """
    config = ConfigParser()
    config_file = Path(config_path)
    
    if config_file.exists():
        config.read(config_file, encoding='utf-8')
    else:
        # 如果配置文件不存在，返回默认配置
        logger = logging.getLogger("netease_vip_manager")
        logger.warning(f"配置文件 {config_path} 不存在，将使用默认配置")
    
    return config


def save_cache(data: Any, cache_file: str = ".cache/auth.json") -> None:
    """
    保存缓存数据到文件
    
    Args:
        data: 要保存的数据
        cache_file: 缓存文件路径
    """
    cache_path = Path(cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(cache_file: str = ".cache/auth.json") -> Any:
    """
    从文件加载缓存数据
    
    Args:
        cache_file: 缓存文件路径
    
    Returns:
        缓存的数据，如果文件不存在返回None
    """
    cache_path = Path(cache_file)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def format_song_info(song: dict) -> str:
    """
    格式化歌曲信息为可读字符串
    
    Args:
        song: 歌曲信息字典
    
    Returns:
        格式化的字符串
    """
    name = song.get('name', '未知歌曲')
    artists = ', '.join([ar.get('name', '') for ar in song.get('ar', [])])
    album = song.get('al', {}).get('name', '未知专辑')
    fee = song.get('fee', 0)
    
    fee_text = {
        0: '免费',
        1: 'VIP',
        4: '购买',
        8: 'VIP高音质'
    }.get(fee, f'未知({fee})')
    
    return f"{name} - {artists} [{album}] ({fee_text})"


def confirm_action(message: str, default: bool = False) -> bool:
    """
    询问用户确认操作
    
    Args:
        message: 确认提示消息
        default: 默认选择
    
    Returns:
        用户的选择 (True/False)
    """
    choices = "Y/n" if default else "y/N"
    console.print(f"\n[yellow]{message} [{choices}][/yellow]", end=" ")
    
    try:
        choice = input().strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[red]操作已取消[/red]")
        return False
    
    if not choice:
        return default
    
    return choice in ['y', 'yes', '是']
