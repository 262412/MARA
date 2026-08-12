import assert from "node:assert/strict";
import test from "node:test";

import { renderInDom } from "../test-dom";
import { AssistantMarkdown } from "./AssistantMarkdown";

test("renders promised Markdown and local math as semantic DOM", async () => {
  const rendered = await renderInDom(
    <AssistantMarkdown
      content={`# Heading

- one
- two

> quoted

| A | B |
| - | - |
| 1 | 2 |

**bold** ~~removed~~ \`inline\`

\`\`\`ts
const value = 1;
\`\`\`

Inline $x^2$ and block:

$$y = mx + b$$

[safe](https://example.com) 【1】 <a href='#' class='citation' id='mark-2'>【2】</a>`}
    />,
  );
  try {
    const document = rendered.document;
    assert.equal(document.querySelector("h1")?.textContent, "Heading");
    assert.equal(document.querySelectorAll("ul > li").length, 2);
    assert.equal(document.querySelector("blockquote")?.textContent?.trim(), "quoted");
    assert.equal(document.querySelectorAll("table tbody td").length, 2);
    assert.ok(document.querySelector("strong"));
    assert.ok(document.querySelector("del"));
    assert.ok(document.querySelector("pre > code.language-ts"));
    assert.ok(document.querySelector(".katex"));
    assert.equal(
      document.querySelector<HTMLAnchorElement>("a")?.href,
      "https://example.com/",
    );
    assert.match(document.body.textContent ?? "", /【1】/);
    assert.match(document.body.textContent ?? "", /【2】/);
    assert.equal(document.querySelectorAll("a").length, 1);
  } finally {
    await rendered.cleanup();
  }
});

test("never renders raw HTML, executable links, or remote images", async () => {
  const rendered = await renderInDom(
    <AssistantMarkdown
      content={`<script>globalThis.pwned = true</script>
<img src=x onerror="globalThis.pwned = true">
![remote](https://attacker.invalid/a.png)
[js](javascript:alert(1)) [data](data:text/html,boom) [file](file:///etc/passwd)`}
    />,
  );
  try {
    const document = rendered.document;
    assert.equal(document.querySelector("script"), null);
    assert.equal(document.querySelector("img"), null);
    assert.equal(document.querySelector("[onerror]"), null);
    for (const link of document.querySelectorAll<HTMLAnchorElement>("a")) {
      assert.ok(!link.hasAttribute("href"));
    }
    assert.equal((globalThis as { pwned?: boolean }).pwned, undefined);
  } finally {
    await rendered.cleanup();
  }
});

test("incomplete streaming Markdown parses safely and converges", async () => {
  const partial = await renderInDom(
    <AssistantMarkdown content={"## Partial\n\n**unfinished\n\n```ts\nconst x = 1"} />,
  );
  try {
    assert.equal(partial.document.querySelector("h2")?.textContent, "Partial");
  } finally {
    await partial.cleanup();
  }

  const complete = await renderInDom(
    <AssistantMarkdown content={"## Partial\n\n**finished**\n\n```ts\nconst x = 1\n```"} />,
  );
  try {
    assert.equal(complete.document.querySelector("strong")?.textContent, "finished");
    assert.ok(complete.document.querySelector("pre > code.language-ts"));
  } finally {
    await complete.cleanup();
  }
});
