from pathlib import Path

from playwright.sync_api import Error, sync_playwright

from app.core.fonts import embedded_vazirmatn_font_faces


PRINT_CSS = """
@page { size: A4; margin: 18mm 17mm; }
html { background: white; color: black; }
body { max-width: none; margin: 0; padding: 0; font-size: 12pt; line-height: 1.8; }
body, p, li, td, th, h1, h2, h3, h4, h5, h6, blockquote, span, a {
  font-family: Vazirmatn, sans-serif !important;
}
p { margin: 0 0 0.7em; orphans: 3; widows: 3; }
h1, h2, h3, h4, h5, h6 { line-height: 1.5; break-after: avoid; }
table { border-collapse: collapse; max-width: 100%; margin-block: 1em; }
td, th { border: 0.5pt solid #999; padding: 0.35em 0.6em; vertical-align: top; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
img, svg { max-width: 100%; height: auto; }
figure { break-inside: avoid; margin-inline: 0; }
pre, code { direction: ltr; unicode-bidi: isolate; font-family: monospace !important; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; text-align: left; }
ul, ol { padding-inline-start: 1.75em; padding-inline-end: 0; }
blockquote { margin-inline: 1.5em; }
a { overflow-wrap: anywhere; }
bdi { unicode-bidi: isolate; }
"""


PREPARE_DOCUMENT = r"""() => {
  const direction = (text, fallback = 'ltr') => {
    const sample = text.replace(/https?:\/\/\S+|\b[\w.+-]+@[\w.-]+\b/g, '');
    let rtl = 0, ltr = 0;
    for (const char of sample) {
      if (!/\p{L}/u.test(char)) continue;
      if (/\p{Script=Arabic}|\p{Script=Hebrew}/u.test(char)) rtl++;
      else ltr++;
    }
    return rtl + ltr ? (rtl > ltr ? 'rtl' : 'ltr') : fallback;
  };
  document.documentElement.dir = direction(document.body.textContent);
  document.documentElement.lang = document.documentElement.dir === 'rtl' ? 'fa' : 'en';
  for (const element of document.querySelectorAll('table,ul,ol,blockquote,p,h1,h2,h3,h4,h5,h6,li,td,th,figcaption,caption')) {
    const base = element.parentElement.closest('[dir]')?.dir || document.documentElement.dir;
    element.dir = direction(element.textContent, base);
    element.style.direction = element.dir;
    if (!['center', 'justify'].includes(element.style.textAlign)) {
      element.style.textAlign = element.dir === 'rtl' ? 'right' : 'left';
    }
  }
  for (const element of document.querySelectorAll('pre,code')) element.dir = 'ltr';
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const latin = /(?:https?:\/\/[^\s<>]+|[A-Za-z0-9]+(?:[ .:/@_+#=\-]+[A-Za-z0-9]+)*)/g;
  for (const node of nodes) {
    if (node.parentElement.closest('script,style,pre,code,bdi')) continue;
    if (node.parentElement.closest('[dir]')?.dir !== 'rtl') continue;
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const match of node.textContent.matchAll(latin)) {
      fragment.append(node.textContent.slice(offset, match.index));
      const isolate = document.createElement('bdi');
      isolate.dir = 'ltr';
      isolate.textContent = match[0];
      fragment.append(isolate);
      offset = match.index + match[0].length;
    }
    if (offset) {
      fragment.append(node.textContent.slice(offset));
      node.replaceWith(fragment);
    }
  }
}"""


def write_html_pdf(html, path):
    with sync_playwright() as playwright:
        if Path(playwright.chromium.executable_path).exists():
            browser = playwright.chromium.launch(headless=True)
        else:
            try:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            except Error as exc:
                raise RuntimeError("برای ساخت PDF فارسی، دستور python -m playwright install chromium را اجرا کنید.") from exc
        try:
            context = browser.new_context(java_script_enabled=False)
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            styles = embedded_vazirmatn_font_faces() + f"<style>{PRINT_CSS}</style>"
            html = html.replace("</head>", styles + "</head>") if "</head>" in html else styles + html
            page.set_content(html, wait_until="load")
            page.evaluate(PREPARE_DOCUMENT)
            page.evaluate("""async () => {
              await Promise.race([
                Promise.all([document.fonts.load('12pt Vazirmatn'), document.fonts.load('bold 12pt Vazirmatn'), document.fonts.ready]),
                new Promise((resolve, reject) => setTimeout(() => reject(new Error('Font loading timed out')), 15000))
              ]);
            }""")
            page.pdf(path=str(path), format="A4", print_background=True, prefer_css_page_size=True, tagged=True)
        finally:
            browser.close()
    return path
