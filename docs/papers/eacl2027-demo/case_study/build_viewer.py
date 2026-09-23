"""Build a standalone presentation from the captured evidence, without new calls."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).parent

STYLE = """
body{margin:0;background:#f3f5f7;color:#172d38;font:16px/1.55 system-ui,sans-serif}
main{max-width:1060px;margin:auto;padding:38px 26px}h1{font-size:36px;line-height:1.15;max-width:880px}
h2{font-size:23px}h3{font-size:18px}.eyebrow{color:#315a69;font-size:13px;letter-spacing:.08em;text-transform:uppercase}
.lead{font-size:19px;max-width:900px}.note{font-size:14px;color:#465f6d}.panel{background:white;border:1px solid #d5dfe4;border-radius:12px;padding:22px;margin:20px 0}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}button{font:inherit;cursor:pointer;padding:9px 14px;border:1px solid #b7cbd4;background:white;border-radius:8px;color:#254758}
button[aria-pressed=true]{background:#194d61;color:white}.step{display:none}.step.active{display:block}blockquote{margin:12px 0;border-left:4px solid #bb7737;padding:8px 16px;background:#fff8ef}
table{width:100%;border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid #dfe7eb;padding:9px 12px}th{background:#eef4f6}td:first-child{font-weight:600}
code{font-size:14px;background:#edf2f4;padding:2px 5px;border-radius:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace;background:#edf2f4;padding:16px}
details{margin:16px 0}summary{cursor:pointer;font-weight:600}a{color:#14617c}footer{padding:24px 0;color:#526a77;font-size:14px}
@media(max-width:650px){main{padding:20px 14px}h1{font-size:29px}table{font-size:13px}td,th{padding:7px 4px}}
"""

SCRIPT = """
document.querySelectorAll('nav button').forEach(button=>button.addEventListener('click',()=>{
 document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.querySelectorAll('.step').forEach(section=>section.classList.toggle('active',section.id===button.dataset.target));
}));
"""


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def raw_details(label, answers):
    parts = []
    for field in [
        "raw_provider_text",
        "pre_verification_answer",
        "pre_guardrail_answer",
        "answer_for_user",
        "answer_for_scoring",
    ]:
        value = answers[field]
        if isinstance(value, list):
            value = "\n\n".join(value)
        parts.append(f"<h3>{html.escape(field)}</h3><pre>{html.escape(value)}</pre>")
    return f"<details><summary>{label}: all retained answer stages</summary>{''.join(parts)}</details>"


def build():
    stages = load("records/answer-stages.json")
    before = load("records/before-response.json")
    after = load("records/after-response.json")
    quote = html.escape(before["answer"])
    answer = html.escape(after["answer"])
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>MARA diagnostic walkthrough</title><style>{STYLE}</style>
<main><div class="eyebrow">MARA · Captured diagnostic case · 23 September 2026</div>
<h1>Why did successful retrieval still end in a refusal?</h1>
<p class="lead">Follow one unresolved question from the displayed answer to its evidence, the blocking decision, and a source correction.</p>
<p class="note">An author-constructed task, executed with real APIs on the installed reviewer build. This page presents captured records; it is not an additional native MARA interface or a new model execution.</p>
<div class="panel"><strong>Question</strong><p>For how many days does the Harbor sensor pilot retain raw sensor logs?</p>
<a href="inputs/harbor-operations.txt">Operating guide</a> · <a href="inputs/harbor-data-policy.txt">Data policy</a></div>
<nav aria-label="Diagnostic steps">{''.join(f'<button data-target="step{i}" aria-pressed="{str(i == 1).lower()}">{i}. {name}</button>' for i,name in enumerate(['Notice','Inspect','Diagnose','Act','Verify'],1))}</nav>
<section class="panel step active" id="step1"><h2>1. The user's task is unresolved</h2><p>Only the operating guide is selected. MARA displays:</p><blockquote>{quote}</blockquote><p>The user needs a retention duration. This message alone suggests a retrieval problem.</p></section>
<section class="panel step" id="step2"><h2>2. Inspect the stages separately</h2><p>Open <a href="records/before-response.json">before-response.json</a>. The selected route is <code>doc_text</code>, retrieval is <code>good</code>, and the <a href="records/before-provider-calls.json">text-provider call</a> completed. Verification is <code>unknown</code>; the guardrail chooses <code>abstain</code>.</p><p>The refusal therefore does not mean that no document was retrieved or that the provider was unavailable.</p></section>
<section class="panel step" id="step3"><h2>3. Find the missing support</h2><p>Inspect <code>evidence_bundle.items</code>. It contains the selected operating guide, including:</p><blockquote>Data retention is specified in the separate Harbor data policy; this operating guide does not state a duration.</blockquote><p>The source scope lacks the requested fact. The model's raw answer already acknowledges this; subsequent verification and guardrails produce the generic refusal. The retrieved document is relevant, but relevance alone is not answer support.</p></section>
<section class="panel step" id="step4"><h2>4. Correct the selected source</h2><p>Select <a href="inputs/harbor-data-policy.txt">harbor-data-policy.txt</a> and ask the same question in a fresh conversation. Keep the provider, automatic route policy and strict verification unchanged.</p><p>The serialized requests differ only in <code>selected_file_ids</code>. This is a user-directed correction, not automatic route recovery.</p></section>
<section class="panel step" id="step5"><h2>5. Verify the observed result</h2><blockquote>{answer}</blockquote><p>Retrieval remains <code>good</code>; verification becomes <code>supported</code>; the guardrail returns the answer. The selected route is still <code>doc_text</code>.</p><p>Check the source sentence yourself. The source text supports 17 days. A supported flag alone is not a general factuality guarantee.</p></section>
<section class="panel"><h2>Recorded comparison</h2><table><tr><th>Field</th><th>Before</th><th>After</th></tr>
<tr><td>Selected document</td><td>Operating guide</td><td>Data policy</td></tr><tr><td>Evidence route</td><td>doc_text</td><td>doc_text</td></tr><tr><td>Retrieval</td><td>good</td><td>good</td></tr><tr><td>Verification</td><td>unknown</td><td>supported</td></tr><tr><td>Guardrail</td><td>abstain</td><td>return</td></tr><tr><td>Automatic route switch</td><td>No</td><td>No</td></tr></table></section>
<section class="panel"><h2>Keep generated, processed and displayed answers distinct</h2>
{raw_details('Before',stages['before'])}{raw_details('After',stages['after'])}
<p class="note">The case's scoring projection is explicitly identity: the displayed answer is scored. The historical benchmark used other adapters and lacks the corresponding raw answer strings.</p></section>
<section class="panel"><h2>An independent repetition did not recover</h2><p>We also ran the reproduction script in a second empty runtime. With the correct policy selected, the model generated the 17-day fact plus extra explanation. The strict verifier supported the core fact but rejected an extension, and MARA abstained. <a href="repeat/after-response.json">Inspect the repeated response</a> and <a href="repeat/after-provider-calls.json">raw provider output</a>.</p><p>This retained negative result shows that the first observed correction is not a stable recovery guarantee. The records expose which stage prevented an answer in each execution.</p></section>
<section class="panel"><h2>Audit or run again</h2><p><code>python verify_case.py</code> verifies hashes, evidence, answer stages and the source-only request change offline. It recomputes fixture checks from raw strings. For a new model execution, follow <a href="README.md">README.md</a>.</p>
<p><a href="records/effective-config.json">Effective configuration</a> · <a href="records/source-verification.json">Installed source checks</a> · <a href="upstream/COMPARISON.md">Kotaemon task comparison</a> · <a href="records/after-response.json">Complete after record</a></p></section>
<footer>This case does not establish multimodal accuracy, a usability improvement, automatic recovery, or the cause of the historical SlideVQA ties. The original demonstration video remains unchanged.</footer></main><script>{SCRIPT}</script></html>"""
    (ROOT / "walkthrough.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    build()
