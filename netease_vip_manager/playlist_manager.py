"""
歌单管理模块
管理VIP歌单的创建和歌曲操作
"""

import logging
import time
from typing import List, Optional
from pyncm import apis
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .utils import retry_on_error

console = Console()
logger = logging.getLogger("netease_vip_manager")


class PlaylistManager:
    """歌单管理器"""
    
    def __init__(self, user_id: int):
        """
        初始化歌单管理器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
    
    @retry_on_error(max_retries=3)
    def get_playlist_by_name(self, name: str) -> Optional[int]:
        """
        根据名称查找歌单
        
        Args:
            name: 歌单名称
        
        Returns:
            歌单ID，未找到返回None
        """
        result = apis.user.GetUserPlaylists(self.user_id, limit=1000)
        
        if result.get('code') != 200:
            logger.error(f"获取歌单列表失败: {result}")
            return None
        
        playlists = result.get('playlist', [])
        
        for playlist in playlists:
            # 只查找自己创建的歌单
            if playlist.get('userId') == self.user_id and playlist.get('name') == name:
                return playlist['id']
        
        return None
    
    @retry_on_error(max_retries=3)
    def create_playlist(self, name: str, description: str = "") -> int:
        """
        创建新歌单
        
        Args:
            name: 歌单名称
            description: 歌单描述
        
        Returns:
            新创建的歌单ID
        """
        logger.info(f"正在创建歌单: {name}")
        
        result = apis.playlist.CreatePlaylist(name)
        
        if result.get('code') != 200:
            raise Exception(f"创建歌单失败: {result}")
        
        playlist_id = result.get('id') or result.get('playlist', {}).get('id')
        
        if not playlist_id:
            raise Exception("创建歌单成功但未获取到歌单ID")
        
        console.print(f"[green]✓ 已创建歌单: {name} (ID: {playlist_id})[/green]")
        logger.info(f"成功创建歌单 ID: {playlist_id}")
        
        return playlist_id
    
    def get_or_create_playlist(self, name: str) -> int:
        """
        获取或创建歌单
        
        Args:
            name: 歌单名称
        
        Returns:
            歌单ID
        """
        # 先尝试查找
        playlist_id = self.get_playlist_by_name(name)
        
        if playlist_id:
            console.print(f"[cyan]找到现有歌单: {name} (ID: {playlist_id})[/cyan]")
            return playlist_id
        
        # 不存在则创建
        return self.create_playlist(name)
    
    @retry_on_error(max_retries=3)
    def add_songs_to_playlist(
        self,
        playlist_id: int,
        song_ids: List[int],
        batch_size: int = 50,
        delay: float = 0.5
    ) -> dict:
        """
        批量添加歌曲到歌单
        
        Args:
            playlist_id: 歌单ID
            song_ids: 歌曲ID列表
            batch_size: 每批次添加的歌曲数量
            delay: 每次请求的延迟（秒）
        
        Returns:
            结果统计 {success: int, failed: int, failed_ids: List[int]}
        """
        if not song_ids:
            logger.warning("没有歌曲需要添加")
            return {'success': 0, 'failed': 0, 'failed_ids': []}
        
        console.print(f"\n[cyan]═══ 添加 {len(song_ids)} 首歌曲到歌单 ═══[/cyan]\n")
        
        success_count = 0
        failed_count = 0
        failed_ids = []
        
        # 动态延迟设置
        current_delay = delay
        base_delay = delay
        max_delay = 5.0
        
        # 分批处理
        batches = [song_ids[i:i + batch_size] for i in range(0, len(song_ids), batch_size)]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]添加歌曲...",
                total=len(song_ids)
            )
            
            for batch_idx, batch in enumerate(batches, 1):
                retry_count = 0
                max_retries = 2
                
                while retry_count <= max_retries:
                    try:
                        # 调用API添加歌曲
                        result = apis.playlist.SetManipulatePlaylistTracks(batch, playlist_id, op='add')
                        
                        if result.get('code') == 200 or result.get('status') == 200:
                            success_count += len(batch)
                            progress.update(task, advance=len(batch))
                            break  # 成功，跳出重试循环
                        elif result.get('code') in [405, 429]:  # 操作频繁或限流
                            retry_count += 1
                            if retry_count <= max_retries:
                                # 阶梯式等待
                                retry_wait = min(5 * retry_count, 15)
                                logger.warning(f"批次 {batch_idx} 操作频繁，等待{retry_wait}秒后重试 ({retry_count}/{max_retries})...")
                                time.sleep(retry_wait)
                                
                                # 增加基础延迟
                                old_delay = current_delay
                                current_delay = min(current_delay + 0.5, max_delay)
                                if old_delay != current_delay:
                                    logger.info(f"调整批次间延迟: {old_delay:.1f}s -> {current_delay:.1f}s")
                            else:
                                logger.warning(f"批次 {batch_idx} 重试{max_retries}次后仍失败: {result}")
                                failed_count += len(batch)
                                failed_ids.extend(batch)
                                progress.update(task, advance=len(batch))
                        else:
                            logger.warning(f"批次 {batch_idx} 添加失败: {result}")
                            failed_count += len(batch)
                            failed_ids.extend(batch)
                            progress.update(task, advance=len(batch))
                            break
                    
                    except Exception as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.error(f"批次 {batch_idx} 添加异常，重试 ({retry_count}/{max_retries}): {e}")
                            time.sleep(3 * retry_count)
                        else:
                            logger.error(f"批次 {batch_idx} 添加失败: {e}")
                            failed_count += len(batch)
                            failed_ids.extend(batch)
                            progress.update(task, advance=len(batch))
                            break
                
                # 批次间延迟
                if batch_idx < len(batches):
                    time.sleep(current_delay)
        
        console.print(f"\n[green]✓ 成功添加 {success_count} 首歌曲[/green]")
        if failed_count > 0:
            console.print(f"[red]✗ 失败 {failed_count} 首歌曲[/red]")
        
        return {
            'success': success_count,
            'failed': failed_count,
            'failed_ids': failed_ids
        }
    
    @retry_on_error(max_retries=3)
    def unlike_songs(
        self,
        song_ids: List[int],
        batch_size: int = 50,
        delay: float = 0.5
    ) -> dict:
        """
        批量取消歌曲喜欢
        
        Args:
            song_ids: 歌曲ID列表
            batch_size: 每批次处理的歌曲数量
            delay: 每次请求的延迟（秒）
        
        Returns:
            结果统计 {success: int, failed: int, failed_ids: List[int]}
        """
        if not song_ids:
            logger.warning("没有歌曲需要取消喜欢")
            return {'success': 0, 'failed': 0, 'failed_ids': []}
        
        console.print(f"\n[cyan]═══ 取消 {len(song_ids)} 首歌曲的喜欢标记 ═══[/cyan]\n")
        
        success_count = 0
        failed_count = 0
        failed_ids = []
        
        # 动态延迟设置
        current_delay = delay
        base_delay = delay
        max_delay = 5.0  # 最大基础延迟
        
        # 频繁操作计数器和连续成功计数器
        rate_limit_count = 0  # 触发频繁操作的次数
        consecutive_success = 0  # 连续成功次数
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]取消喜欢...",
                total=len(song_ids)
            )
            
            # 逐个处理（网易云的like API通常是单个歌曲）
            for idx, song_id in enumerate(song_ids, 1):
                try:
                    # 如果不是第一首，先延迟
                    if idx > 1:
                        time.sleep(current_delay)
                    
                    # 调用API取消喜欢（like=False）
                    result = apis.track.SetLikeTrack(song_id, like=False)
                    
                    if result.get('code') == 200:
                        success_count += 1
                        consecutive_success += 1
                        
                        # 连续成功3次后，尝试降低延迟
                        if consecutive_success >= 3 and current_delay > base_delay:
                            old_delay = current_delay
                            current_delay = max(base_delay, current_delay * 0.7)
                            logger.info(f"连续成功{consecutive_success}次，降低延迟: {old_delay:.1f}s -> {current_delay:.1f}s")
                            consecutive_success = 0
                        
                    elif result.get('code') == 405:
                        # 操作频繁，重置连续成功计数
                        consecutive_success = 0
                        rate_limit_count += 1
                        
                        # 阶梯式增加等待时间: 5s, 10s, 15s, 20s, 25s...
                        retry_wait = min(5 + (rate_limit_count - 1) * 5, 30)
                        logger.warning(f"歌曲 {song_id} 操作频繁 (第{rate_limit_count}次)，等待{retry_wait}秒后重试...")
                        time.sleep(retry_wait)
                        
                        # 同时增加基础延迟
                        old_delay = current_delay
                        current_delay = min(current_delay + 0.5, max_delay)
                        if old_delay != current_delay:
                            logger.info(f"调整基础延迟: {old_delay:.1f}s -> {current_delay:.1f}s")
                        
                        # 重试
                        retry_result = apis.track.SetLikeTrack(song_id, like=False)
                        if retry_result.get('code') == 200:
                            success_count += 1
                            logger.debug(f"歌曲 {song_id} 重试成功")
                        elif retry_result.get('code') == 405:
                            # 重试还是频繁，再等更久
                            rate_limit_count += 1
                            second_retry_wait = min(10 + (rate_limit_count - 1) * 5, 60)
                            logger.warning(f"歌曲 {song_id} 重试仍然频繁，等待{second_retry_wait}秒...")
                            time.sleep(second_retry_wait)
                            
                            # 第二次重试
                            second_retry_result = apis.track.SetLikeTrack(song_id, like=False)
                            if second_retry_result.get('code') == 200:
                                success_count += 1
                                logger.debug(f"歌曲 {song_id} 第二次重试成功")
                            else:
                                logger.warning(f"歌曲 {song_id} 取消喜欢失败 (两次重试后): {second_retry_result}")
                                failed_count += 1
                                failed_ids.append(song_id)
                        else:
                            logger.warning(f"歌曲 {song_id} 取消喜欢失败: {retry_result}")
                            failed_count += 1
                            failed_ids.append(song_id)
                    else:
                        # 其他错误，重置连续成功计数
                        consecutive_success = 0
                        logger.warning(f"歌曲 {song_id} 取消喜欢失败: {result}")
                        failed_count += 1
                        failed_ids.append(song_id)
                    
                    progress.update(task, advance=1)
                
                except Exception as e:
                    consecutive_success = 0
                    logger.error(f"歌曲 {song_id} 取消喜欢失败: {e}")
                    failed_count += 1
                    failed_ids.append(song_id)
                    progress.update(task, advance=1)
        
        console.print(f"\n[green]✓ 成功取消 {success_count} 首歌曲的喜欢[/green]")
        if failed_count > 0:
            console.print(f"[red]✗ 失败 {failed_count} 首歌曲[/red]")
        
        return {
            'success': success_count,
            'failed': failed_count,
            'failed_ids': failed_ids
        }
    
    @retry_on_error(max_retries=3)
    def get_playlist_track_ids(self, playlist_id: int) -> List[int]:
        """
        获取歌单中的所有歌曲ID
        
        Args:
            playlist_id: 歌单ID
        
        Returns:
            歌曲ID列表
        """
        result = apis.playlist.GetPlaylistAllTracks(playlist_id)
        
        if result.get('code') != 200:
            logger.error(f"获取歌单歌曲失败: {result}")
            return []
        
        songs = result.get('songs', [])
        return [song['id'] for song in songs if 'id' in song]
    
    def add_songs_incrementally(
        self,
        playlist_id: int,
        song_ids: List[int],
        **kwargs
    ) -> dict:
        """
        增量添加歌曲（跳过已存在的）
        
        Args:
            playlist_id: 歌单ID
            song_ids: 要添加的歌曲ID列表
            **kwargs: 传递给add_songs_to_playlist的其他参数
        
        Returns:
            结果统计
        """
        # 获取歌单现有歌曲
        existing_ids = set(self.get_playlist_track_ids(playlist_id))
        
        # 过滤已存在的歌曲
        new_song_ids = [sid for sid in song_ids if sid not in existing_ids]
        
        if not new_song_ids:
            console.print("[yellow]所有歌曲已存在于歌单中，无需添加[/yellow]")
            return {'success': 0, 'failed': 0, 'failed_ids': [], 'skipped': len(song_ids)}
        
        skipped_count = len(song_ids) - len(new_song_ids)
        if skipped_count > 0:
            console.print(f"[dim]跳过 {skipped_count} 首已存在的歌曲[/dim]")
        
        result = self.add_songs_to_playlist(playlist_id, new_song_ids, **kwargs)
        result['skipped'] = skipped_count
        
        return result
