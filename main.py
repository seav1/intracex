import os
import time
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError

def handle_consent_popup(page, timeout=10000):
    """
    处理 Cookie 同意弹窗
    """
    try:
        consent_button_selector = 'button.fc-cta-consent.fc-primary-button'
        print("检查是否有 Cookie 同意弹窗...")
        page.wait_for_selector(consent_button_selector, state='visible', timeout=timeout)
        print("发现 Cookie 同意弹窗，正在点击'同意'按钮...")
        page.click(consent_button_selector)
        print("已点击'同意'按钮。")
        time.sleep(2)
        return True
    except Exception:
        print("未发现 Cookie 同意弹窗或已处理过")
        return False

def is_login_page(page):
    """
    检测当前页面是否显示登录表单，用于判断 cookie 是否失效。
    至少匹配两个核心元素 (邮箱、密码、提交按钮) 则认为是登录页。
    """
    login_selectors = [
        'input#email[type="email"][name="email"]',
        'input#password[type="password"][name="password"]',
        'input.btn.btn-primary.btn-block[type="submit"][value="Anmelden"]'
    ]
    matches = 0
    try:
        for selector in login_selectors:
            if page.query_selector(selector):
                matches += 1
        if matches >= 2:
            print(f"检测到登录表单 (匹配数量: {matches})")
            return True
        return False
    except Exception as e:
        print(f"检测登录表单时出错: {e}")
        return False

def safe_goto(page, url, wait_until="domcontentloaded", timeout=90000):
    """
    安全的页面导航,带重试机制
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            print(f"正在访问: {url} (尝试 {attempt + 1}/{max_retries})")
            page.goto(url, wait_until=wait_until, timeout=timeout)
            print(f"页面加载成功: {page.url}")
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

def parse_cookies_from_env(cookie_string):
    """
    从环境变量中解析 cookie 字符串
    格式: "name1=value1; name2=value2"
    """
    cookies = []
    if not cookie_string:
        return cookies
    cookie_pairs = cookie_string.split('; ')
    for pair in cookie_pairs:
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '.intracex.de',
                'path': '/',
                'expires': time.time() + 3600 * 24 * 365,
                'httpOnly': True,
                'secure': True,
                'sameSite': 'Lax'
            })
    return cookies

def get_cookies_string(context):
    """
    从浏览器 context 中提取 cookies 并转换为字符串格式
    """
    cookies = context.cookies()
    cookie_pairs = []
    for cookie in cookies:
        if cookie.get('domain') and 'intracex.de' in cookie['domain']:
            cookie_pairs.append(f"{cookie['name']}={cookie['value']}")
    return '; '.join(cookie_pairs)

def save_new_cookie(context):
    """
    保存新的 cookie 到文件
    """
    try:
        new_cookie = get_cookies_string(context)
        if new_cookie:
            with open('new_cookie.txt', 'w') as f:
                f.write(new_cookie)
            print(f"✅ 已保存新 cookie 到 new_cookie.txt (长度: {len(new_cookie)})")
            return True
    except Exception as e:
        print(f"保存 cookie 失败: {e}")
    return False

def add_server_time(server_url="https://intracex.de/minecraft"):
    """
    尝试使用 REMEMBER_WEB_COOKIE 登录 intracex.de 并点击 "Verlängern" 按钮。
    若检测到登录表单则认定 cookie 失效，不再尝试账号密码登录。
    """
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')

    if not remember_web_cookie:
        print("错误: 缺少 REMEMBER_WEB_COOKIE 环境变量，无法登录。")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # --- 优先使用 cookie 登录 ---
            if remember_web_cookie:
                print("尝试使用 REMEMBER_WEB_COOKIE 会话登录...")
                cookies = parse_cookies_from_env(remember_web_cookie)
                if cookies:
                    context.add_cookies(cookies)
                    print(f"已设置 {len(cookies)} 个 cookies。正在访问 {server_url}")
                    if not safe_goto(page, server_url):
                        print("使用 REMEMBER_WEB_COOKIE 访问失败。")
                        page.screenshot(path="cookie_login_fail_navigation.png")
                        return False
                    time.sleep(3)
                    if "login" in page.url or "auth" in page.url or is_login_page(page):
                        print("检测到登录表单，REMEMBER_WEB_COOKIE 失效。")
                        page.screenshot(path="cookie_invalid_login_page.png")
                        return False
                    print("REMEMBER_WEB_COOKIE 登录成功。")
                else:
                    print("REMEMBER_WEB_COOKIE 解析失败，未设置有效 cookies。")
                    return False

            # --- 已经进入服务器页面 ---
            print(f"当前页面URL: {page.url}")
            time.sleep(3)
            page.screenshot(path="step1_page_loaded.png")

            # --- 查找并点击 Verlängern 按钮 ---
            add_button_selector = 'button:has-text("Verlängern"), a:has-text("Verlängern"), [role="button"]:has-text("Verlängern")'
            print("正在查找 'Verlängern' 按钮...")

            try:
                page.wait_for_selector(add_button_selector, timeout=30000)
                button = page.query_selector(add_button_selector)

                if not button:
                    print("按钮查询失败。")
                    page.screenshot(path="extend_button_not_found.png")
                    return False

                # 检查 class 属性是否包含 disabled
                button_class = button.get_attribute("class") or ""
                print(f"按钮 class 属性: {button_class}")

                if "disabled" in button_class:
                    print("按钮已禁用，无需续期。")
                    return True

                print("按钮可点击，正在点击...")
                button.click()
                print("成功点击 'Verlängern' 按钮，已续期。")
                time.sleep(5)
                page.screenshot(path="extend_success.png")
                return True

            except Exception as e:
                print(f"操作过程中发生错误: {e}")
                page.screenshot(path="extend_button_error.png")
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
