"""
小红书平台发布服务
"""
import html as _html
import re
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Page

from .base import BasePlatformPublisher
from app.models.publish import PlatformAccount


class XiaohongshuPublisher(BasePlatformPublisher):
    """小红书平台发布实现"""

    @staticmethod
    def _html_to_plain(text: str) -> str:
        """
        将可能包含 HTML 标记的内容转为纯文本，供小红书长文编辑器使用。
        前端发布时优先传入 rendered_content（带 <p>/<strong>/<br> 等标签），
        直接输入编辑器会导致发布被平台拒绝，必须先还原为纯文本。
        """
        if not text:
            return ""
        t = re.sub(r"(?i)<br\s*/?>", "\n", text)
        t = re.sub(r"(?i)</(p|div|h[1-6]|li|blockquote|tr)>", "\n", t)
        t = re.sub(r"<[^>]+>", "", t)
        t = _html.unescape(t)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()
    
    def get_platform_name(self) -> str:
        return "小红书"
    
    def get_login_url(self) -> str:
        return "https://creator.xiaohongshu.com/login"
    
    async def validate_cookies(self, account: PlatformAccount) -> bool:
        """验证小红书Cookie有效性"""
        cookies = self.get_cookies(account)
        if not cookies:
            return False
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                # 设置Cookie
                await context.add_cookies([
                    {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
                    for k, v in cookies.items()
                ])
                
                page = await context.new_page()
                
                # 访问创作者中心，检查是否需要登录
                # 不等待 networkidle：小红书页面有持续网络请求，等待网络空闲会超时
                await page.goto("https://creator.xiaohongshu.com/creator/home", timeout=60000, wait_until="domcontentloaded")
                # 给页面跳转留时间，再判断是否进入登录页
                await page.wait_for_timeout(2000)
                
                # 检查是否跳转到登录页
                current_url = page.url
                is_valid = "login" not in current_url.lower()
                
                await browser.close()
                return is_valid
                
        except Exception as e:
            self.logger.error(f"验证小红书Cookie失败: {str(e)}")
            return False
    
    async def create_draft(
        self,
        account: PlatformAccount,
        title: str,
        content: str,
        cover_image: Optional[str] = None,
        media_urls: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发布小红书长文笔记

        小红书新版发布页是"选择发布类型"引导页：图文笔记必须先上传图片
        才会出现标题/正文编辑器，纯文字"写长文"可直接进入编辑器。
        这里走"写长文 -> 新的创作"路径，不依赖配图。

        Args:
            account: 平台账号
            title: 长文笔记标题（最多 64 字）
            content: 长文笔记正文（纯文本/Markdown）
            cover_image: 封面图 URL（长文路径不使用）
            media_urls: 图片 URLs（长文路径不使用）
            tags: 标签列表（长文路径不使用）

        Returns:
            Dict: 草稿信息
        """
        try:
            # 检查Cookie，失败统一走"创建失败"返回，避免抛 500
            cookies = await self.check_cookies_or_raise(account)
            # 前端传入的可能是 HTML 渲染内容，必须先转为纯文本
            content = self._html_to_plain(content or "")

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    # 完整 UA（含 Chrome 版本号）：缺失会被小红书判定为旧浏览器，
                    # 无头模式下"一键排版"等核心功能会被静默拦截
                    user_agent=(
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/151.0.7922.138 Safari/537.36'
                    )
                )

                # 设置Cookie
                await context.add_cookies([
                    {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
                    for k, v in cookies.items()
                ])

                # "发布"按钮渲染在封闭式 shadow DOM 中（xhs-publish-btn 自定义元素），
                # 普通选择器无法读取/点击；注入补丁将其改为开放 shadow DOM
                await context.add_init_script(
                    """
                    (() => {
                      const orig = Element.prototype.attachShadow;
                      if (orig) {
                        Element.prototype.attachShadow = function(init) {
                          try { init.mode = 'open'; } catch (e) {}
                          return orig.call(this, init);
                        };
                      }
                    })();
                    """
                )

                page = await context.new_page()
                page.set_default_timeout(60000)

                # 打开发布页；新版发布页为"选择发布类型"引导页
                await page.goto(
                    "https://creator.xiaohongshu.com/publish/publish",
                    timeout=60000,
                    wait_until="domcontentloaded"
                )

                # 等待发布页可交互（出现"写长文"入口）
                await page.wait_for_selector('text=写长文', timeout=60000)

                # 关闭"未绑定手机号"等提示弹窗（如出现）
                try:
                    modal = page.locator('text=我了解了')
                    if await modal.count() > 0:
                        await modal.first.evaluate("el => el.click()")
                        await page.wait_for_timeout(1500)
                except Exception:
                    pass

                # 点击"写长文"，进入长文列表
                await page.locator('text=写长文').first.evaluate("el => el.click()")

                # 点击"新的创作"，进入长文编辑器
                await page.wait_for_selector('text=新的创作', timeout=30000)
                await page.locator('text=新的创作').first.evaluate("el => el.click()")

                # 等待标题输入框出现（长文编辑器标题为 textarea，占位"输入标题"）
                title_input = await page.wait_for_selector(
                    'textarea[placeholder*="输入标题"]',
                    timeout=60000
                )
                # 小红书长文标题最多 64 字
                await title_input.fill((title or "")[:64])

                # 正文为 ProseMirror 富文本编辑器，先聚焦并清空默认段落，再输入正文
                editor = await page.wait_for_selector(
                    'div.tiptap.ProseMirror, [contenteditable="true"].ProseMirror',
                    timeout=30000
                )
                await editor.click()
                await page.keyboard.press("ControlOrMeta+A")
                await page.keyboard.type(content or "")

                # 点击"一键排版"打开模板面板（必须用 el.click 触发 Vue 事件）
                await page.evaluate(
                    """() => {
                      const btn = [...document.querySelectorAll('button')]
                        .find(b => (b.innerText || '').includes('一键排版'));
                      if (!btn) throw new Error('未找到"一键排版"按钮');
                      btn.click();
                    }"""
                )

                # 等待模板面板出现（出现"选择模板"或"下一步"按钮即视为已打开）
                await page.wait_for_function(
                    """() => document.body.innerText.includes('选择模板')
                        || [...document.querySelectorAll('button')]
                             .some(b => (b.innerText || '').includes('下一步'))""",
                    timeout=60000,
                )

                # 选择第一个版式"理性现代"
                try:
                    tpl = page.locator('text=理性现代').first
                    if await tpl.count() > 0:
                        await tpl.evaluate("el => el.click()")
                        await page.wait_for_timeout(3000)
                except Exception:
                    pass

                # 点击"下一步"进入发布预览/设置页
                nxt = page.locator('button', has_text='下一步').first
                await nxt.wait_for(state='visible', timeout=60000)
                await nxt.evaluate("el => el.click()")

                # 预览页加载需要时间（模板封面渲染/上传），等按钮就绪前先给足缓冲，
                # 过早点击"发布"会被平台忽略（页面仍停留在预览页）
                await page.wait_for_timeout(10000)

                # 等待"发布"按钮组件挂载（xhs-publish-btn 自定义元素）
                await page.locator('xhs-publish-btn').first.wait_for(
                    state='attached', timeout=60000
                )
                await page.wait_for_function(
                    """() => {
                      const el = document.querySelector('xhs-publish-btn');
                      if (!el || !el.shadowRoot) return false;
                      return [...el.shadowRoot.querySelectorAll('button')]
                        .some(b => (b.innerText || '').trim() === '发布' && !b.disabled);
                    }""",
                    timeout=60000,
                )

                # 点击 shadow DOM 内的"发布"按钮
                await page.evaluate(
                    """() => {
                      const el = document.querySelector('xhs-publish-btn');
                      const btn = [...el.shadowRoot.querySelectorAll('button')]
                        .find(b => (b.innerText || '').trim() === '发布');
                      if (!btn) throw new Error('未找到"发布"按钮');
                      btn.click();
                    }"""
                )
                await page.wait_for_timeout(4000)

                # 等待发布成功信号：成功文案或跳转笔记管理页，任一出现即成功
                publish_ok = False
                page_snippet = ''
                for _ in range(18):  # 最长约 90 秒
                    await page.wait_for_timeout(5000)
                    try:
                        page_snippet = await page.evaluate("document.body.innerText")
                    except Exception:
                        page_snippet = ''
                    if any(k in page_snippet for k in ('发布成功', '审核中', '发布完成', '已发布')):
                        publish_ok = True
                        break
                    if 'post-manage' in page.url:
                        publish_ok = True
                        break

                if not publish_ok:
                    raise RuntimeError(
                        f'未检测到发布成功信号，页面片段: {page_snippet[:300]}'
                    )

                await page.wait_for_timeout(2000)

                await browser.close()

                return {
                    "success": True,
                    "draft_id": "draft",  # 小红书不返回具体ID
                    "draft_url": "https://creator.xiaohongshu.com/creator/post-manage",
                    "message": "已发布到小红书，请前往创作者中心查看"
                }

        except Exception as e:
            self.logger.error(f"创建小红书草稿失败: {str(e)}")
            return {
                "success": False,
                "message": f"创建草稿失败: {str(e)}"
            }
