"""
网易云音乐登录认证模块
支持二维码、手机号验证码等多种登录方式
"""

import logging
import time
from typing import Optional, Dict, Any
from pyncm import apis, GetCurrentSession
from pyncm.apis.login import LoginQrcodeUnikey, LoginQrcodeCheck, LoginViaCellphone, LoginViaAnonymousAccount
from rich.console import Console
from rich.table import Table

from .utils import save_cache, load_cache, retry_on_error

console = Console()
logger = logging.getLogger("netease_vip_manager")


class NeteaseAuth:
    """网易云音乐认证管理器"""
    
    def __init__(self, cache_file: str = ".cache/auth.json"):
        """
        初始化认证管理器
        
        Args:
            cache_file: 登录缓存文件路径
        """
        self.cache_file = cache_file
        self.session = GetCurrentSession()
        self.user_info: Optional[Dict[str, Any]] = None
    
    def is_logged_in(self) -> bool:
        """
        检查是否已登录
        
        Returns:
            是否已登录
        """
        try:
            # 尝试获取用户账号信息
            result = apis.user.GetUserAccount()
            if result.get('code') == 200:
                self.user_info = result.get('profile', {})
                return True
        except Exception as e:
            logger.debug(f"登录检查失败: {e}")
        
        return False
    
    def load_session_from_cache(self) -> bool:
        """
        从缓存加载登录会话
        
        Returns:
            是否成功加载
        """
        cache_data = load_cache(self.cache_file)
        
        if not cache_data:
            logger.info("未找到登录缓存")
            return False
        
        try:
            # 恢复cookies
            cookies = cache_data.get('cookies', {})
            for key, value in cookies.items():
                self.session.cookies.set(key, value)
            
            # 验证session是否有效
            if self.is_logged_in():
                logger.info(f"成功恢复登录状态，欢迎 {self.user_info.get('nickname', '用户')}")
                return True
            else:
                logger.warning("登录缓存已过期")
                return False
        
        except Exception as e:
            logger.error(f"加载登录缓存失败: {e}")
            return False
    
    def save_session_to_cache(self) -> None:
        """保存当前登录会话到缓存"""
        try:
            cache_data = {
                'cookies': dict(self.session.cookies),
                'user_info': self.user_info,
                'timestamp': time.time()
            }
            save_cache(cache_data, self.cache_file)
            logger.info("登录状态已保存")
        except Exception as e:
            logger.error(f"保存登录状态失败: {e}")
    
    @retry_on_error(max_retries=3)
    def login_via_qrcode(self) -> bool:
        """
        通过二维码登录
        
        Returns:
            是否登录成功
        """
        console.print("\n[cyan]═══ 二维码登录 ═══[/cyan]\n")
        
        try:
            # 获取二维码key
            unikey_result = LoginQrcodeUnikey()
            if unikey_result.get('code') != 200:
                logger.error("获取二维码key失败")
                return False
            
            unikey = unikey_result['unikey']
            qrcode_url = f"https://music.163.com/login?codekey={unikey}"
            
            console.print(f"[green]请使用网易云音乐APP扫描二维码登录[/green]")
            console.print(f"[dim]二维码链接: {qrcode_url}[/dim]\n")
            
            # 尝试在终端显示二维码
            try:
                import qrcode
                qr = qrcode.QRCode()
                qr.add_data(qrcode_url)
                qr.print_ascii(invert=True)
            except ImportError:
                console.print("[yellow]提示: 安装 qrcode 库可以在终端直接显示二维码[/yellow]")
                console.print(f"[yellow]或者访问: {qrcode_url}[/yellow]\n")
            
            # 轮询检查扫码状态
            console.print("[cyan]等待扫码...[/cyan]")
            
            max_attempts = 60  # 最多等待60次，每次2秒，共2分钟
            for attempt in range(max_attempts):
                time.sleep(2)
                
                check_result = LoginQrcodeCheck(unikey)
                code = check_result.get('code')
                
                if code == 803:  # 授权登录成功
                    console.print("[green]✓ 登录成功![/green]\n")
                    
                    # 获取用户信息
                    if self.is_logged_in():
                        self.save_session_to_cache()
                        self._display_user_info()
                        return True
                    
                elif code == 800:  # 二维码过期
                    console.print("[red]✗ 二维码已过期，请重试[/red]")
                    return False
                
                elif code == 802:  # 已扫码，等待确认
                    console.print("[yellow]已扫码，请在手机上确认...[/yellow]")
                
                # code == 801 表示等待扫码，继续轮询
            
            console.print("[red]✗ 登录超时，请重试[/red]")
            return False
        
        except Exception as e:
            logger.error(f"二维码登录失败: {e}")
            return False
    
    @retry_on_error(max_retries=3)
    def login_via_phone(self, phone: Optional[str] = None) -> bool:
        """
        通过手机号+验证码登录
        
        Args:
            phone: 手机号（可选，未提供则提示输入）
        
        Returns:
            是否登录成功
        """
        console.print("\n[cyan]═══ 手机号登录 ═══[/cyan]\n")
        
        try:
            # 获取手机号
            if not phone:
                console.print("[green]请输入手机号:[/green]", end=" ")
                phone = input().strip()
            
            if not phone:
                logger.error("手机号不能为空")
                return False
            
            # 发送验证码
            from pyncm.apis.login import LoginSendPhoneCode
            
            console.print(f"[cyan]正在向 {phone} 发送验证码...[/cyan]")
            send_result = LoginSendPhoneCode(phone)
            
            if send_result.get('code') != 200:
                logger.error(f"发送验证码失败: {send_result}")
                return False
            
            console.print("[green]✓ 验证码已发送[/green]")
            console.print("[green]请输入验证码:[/green]", end=" ")
            captcha = input().strip()
            
            if not captcha:
                logger.error("验证码不能为空")
                return False
            
            # 登录
            console.print("[cyan]正在登录...[/cyan]")
            login_result = LoginViaCellphone(phone, captcha=captcha)
            
            if login_result.get('code') == 200:
                console.print("[green]✓ 登录成功![/green]\n")
                
                if self.is_logged_in():
                    self.save_session_to_cache()
                    self._display_user_info()
                    return True
            else:
                logger.error(f"登录失败: {login_result.get('message', '未知错误')}")
                return False
        
        except Exception as e:
            logger.error(f"手机号登录失败: {e}")
            return False
    
    def login(self, method: str = "qr_code", **kwargs) -> bool:
        """
        统一登录入口
        
        Args:
            method: 登录方式 (qr_code, phone)
            **kwargs: 其他参数
        
        Returns:
            是否登录成功
        """
        # 先尝试从缓存恢复
        if self.load_session_from_cache():
            return True
        
        # 根据方法选择登录方式
        if method == "qr_code":
            return self.login_via_qrcode()
        elif method == "phone":
            return self.login_via_phone(kwargs.get('phone'))
        else:
            logger.error(f"不支持的登录方式: {method}")
            return False
    
    def _display_user_info(self) -> None:
        """显示用户信息"""
        if not self.user_info:
            return
        
        table = Table(title="用户信息", show_header=False, border_style="cyan")
        table.add_column("属性", style="dim")
        table.add_column("值", style="bold")
        
        table.add_row("昵称", self.user_info.get('nickname', ''))
        table.add_row("用户ID", str(self.user_info.get('userId', '')))
        
        vip_type = self.user_info.get('vipType', 0)
        vip_text = {
            0: '普通用户',
            11: 'VIP会员'
        }.get(vip_type, f'未知({vip_type})')
        table.add_row("会员类型", vip_text)
        
        console.print(table)
    
    def get_user_id(self) -> Optional[int]:
        """
        获取当前用户ID
        
        Returns:
            用户ID，未登录返回None
        """
        if self.user_info:
            return self.user_info.get('userId')
        return None
