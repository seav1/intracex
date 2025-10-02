import os
import time
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError

def handle_consent_popup(page, timeout=10000):
    """
    处理 Cookie 同意弹窗
    """
    try:
        # 等待同意按钮出现
        consent_button_selector = 'button.fc-cta-consent.fc-primary-button'
        print("检查是否有 Cookie 同意弹窗...")
        
        # 使用较短的超时时间，因为弹窗可能不会出现
        page.wait_for_selector(consent_button_selector, state='visible', timeout=timeout)
        print("发现 Cookie 同意弹窗，正在点击'同意'按钮...")
        page.click(consent_button_selector)
        print("已点击'同意'按钮。")
        time.sleep(2)  # 等待弹窗关闭
        return True
    except Exception as e:
        print(f"未发现 Cookie 同意弹窗或已处理过")
        return False

def safe_goto(page, url, wait_until="domcontentloaded", timeout=90000):
    """
    安全的页面导航，带重试机制
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            print(f"正在访问: {url} (尝试 {attempt + 1}/{max_retries})")
            page.goto(url, wait_until=wait_until, timeout=timeout)
            print(f"页面加载成功: {page.url}")
            
            # 处理可能出现的 Cookie 同意弹窗
            handle_consent_popup(page, timeout=5000)
            
            return True
        except PlaywrightTimeoutError:
            print(f"页面加载超时 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                print("等待 5 秒后重试...")
                time.sleep(5)
            else:
                print("达到最大重试次数")
                return False
        except Exception as e:
            print(f"页面导航出错: {e}")
            return False
    return False

def add_server_time(server_url="https://panel.freegamehost.xyz/server/0bb0b9d6"):
    """
    尝试登录 panel.freegamehost.xyz 并点击 "ADD 8 HOURS" 按钮。
    优先使用 REMEMBER_WEB_COOKIE 进行会话登录，如果不存在则回退到邮箱密码登录。
    """
    # 获取环境变量
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    login_email = os.environ.get('LOGIN_EMAIL')
    login_password = os.environ.get('LOGIN_PASSWORD')

    # 检查是否提供了任何登录凭据
    if not (remember_web_cookie or (login_email and login_password)):
        print("错误: 缺少登录凭据。请设置 REMEMBER_WEB_COOKIE 或 LOGIN_EMAIL 和 LOGIN_PASSWORD 环境变量。")
        return False

    with sync_playwright() as p:
        # 在 GitHub Actions 中，通常使用 headless 模式
        # 添加更多浏览器参数以提高稳定性
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        # 设置更长的默认超时
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.set_default_timeout(60000)  # 设置默认超时为 60 秒

        try:
            # --- 尝试通过 REMEMBER_WEB_COOKIE 会话登录 ---
            if remember_web_cookie:
                print("尝试使用 REMEMBER_WEB_COOKIE 会话登录...")
                session_cookie = Cookie(
                    name='remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    value=remember_web_cookie,
                    domain='.freegamehost.xyz',
                    path='/',
                    expires=time.time() + 3600 * 24 * 365,
                    httpOnly=True,
                    secure=True,
                    sameSite='Lax'
                )
                context.add_cookies([session_cookie])
                print(f"已设置 REMEMBER_WEB_COOKIE。正在访问服务器页面: {server_url}")
                
                # 使用 safe_goto 代替直接 goto，使用 domcontentloaded 而非 networkidle
                if not safe_goto(page, server_url, wait_until="domcontentloaded"):
                    print("使用 REMEMBER_WEB_COOKIE 访问服务器页面失败。")
                    remember_web_cookie = None
                else:
                    # 检查是否成功登录并停留在服务器页面
                    time.sleep(3)  # 等待页面稳定
                    if "login" in page.url or "auth" in page.url:
                        print("使用 REMEMBER_WEB_COOKIE 登录失败或会话无效。将尝试使用邮箱密码登录。")
                        context.clear_cookies()
                        remember_web_cookie = None
                    else:
                        print("REMEMBER_WEB_COOKIE 登录成功。")

            # --- 如果 REMEMBER_WEB_COOKIE 不可用或失败，则回退到邮箱密码登录 ---
            if not remember_web_cookie:
                if not (login_email and login_password):
                    print("错误: REMEMBER_WEB_COOKIE 无效，且未提供 LOGIN_EMAIL 或 LOGIN_PASSWORD。无法登录。")
                    return False

                login_url = "https://panel.freegamehost.xyz/auth/login"
                print(f"正在访问登录页: {login_url}")
                
                if not safe_goto(page, login_url, wait_until="domcontentloaded"):
                    print("访问登录页失败。")
                    page.screenshot(path="login_page_load_fail.png")
                    return False

                # 登录表单元素选择器
                email_selector = 'input[name="email"]'
                password_selector = 'input[name="password"]'
                login_button_selector = 'button[type="submit"]'

                print("正在等待登录元素加载...")
                try:
                    page.wait_for_selector(email_selector, timeout=30000)
                    page.wait_for_selector(password_selector, timeout=30000)
                    page.wait_for_selector(login_button_selector, timeout=30000)
                except Exception as e:
                    print(f"等待登录元素失败: {e}")
                    page.screenshot(path="login_elements_not_found.png")
                    return False

                print("正在填充邮箱和密码...")
                page.fill(email_selector, login_email)
                page.fill(password_selector, login_password)

                print("正在点击登录按钮...")
                page.click(login_button_selector)

                try:
                    # 等待导航完成
                    page.wait_for_load_state("domcontentloaded", timeout=60000)
                    time.sleep(3)  # 等待页面稳定
                    
                    # 检查是否登录成功
                    if "login" in page.url or "auth" in page.url:
                        error_message_selector = '.alert.alert-danger, .error-message, .form-error'
                        error_element = page.query_selector(error_message_selector)
                        if error_element:
                            error_text = error_element.inner_text().strip()
                            print(f"邮箱密码登录失败: {error_text}")
                        else:
                            print("邮箱密码登录失败: 未能跳转到预期页面。")
                        page.screenshot(path="login_fail.png")
                        return False
                    else:
                        print("邮箱密码登录成功。")
                        # 导航到服务器页面
                        if page.url != server_url:
                            print(f"正在导航到服务器页面: {server_url}")
                            if not safe_goto(page, server_url, wait_until="domcontentloaded"):
                                print("导航到服务器页面失败。")
                                return False
                except Exception as e:
                    print(f"登录后处理失败: {e}")
                    page.screenshot(path="post_login_error.png")
                    return False

            # --- 确保当前页面是目标服务器页面 ---
            print(f"当前页面URL: {page.url}")
            time.sleep(2)  # 等待页面完全加载

            # --- 查找并点击 "ADD 8 HOURS" 按钮 ---
            add_button_selector = 'button:has-text("ADD 8 HOURS")'
            print(f"正在查找 'ADD 8 HOURS' 按钮...")

            try:
                page.wait_for_selector(add_button_selector, state='visible', timeout=30000)
                print("找到按钮，正在点击...")
                page.click(add_button_selector)
                print("成功点击 'ADD 8 HOURS' 按钮。")
                time.sleep(5)
                print("任务完成。")
                return True
            except Exception as e:
                print(f"未找到 'ADD 8 HOURS' 按钮或点击失败: {e}")
                page.screenshot(path="extend_button_not_found.png")
                
                # 尝试打印页面上所有按钮文本，帮助调试
                try:
                    buttons = page.query_selector_all('button')
                    print(f"页面上找到 {len(buttons)} 个按钮:")
                    for i, btn in enumerate(buttons[:10]):  # 只打印前10个
                        try:
                            text = btn.inner_text().strip()
                            if text:
                                print(f"  按钮 {i+1}: {text}")
                        except:
                            pass
                except:
                    pass
                
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            try:
                page.screenshot(path="general_error.png")
            except:
                pass
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    print("开始执行添加服务器时间任务...")
    success = add_server_time()
    if success:
        print("任务执行成功。")
        exit(0)
    else:
        print("任务执行失败。")
        exit(1)
