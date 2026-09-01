"""The ranking UI: two takes, one keypress.

This is the most valuable thing in the repo. You are the reward model until
there is a dataset, so your throughput as a judge is the rate limiter on
everything downstream - make the judging fast and it stops being the bottleneck.

Deliberately stdlib-only and deliberately plain. Keys: 1 left, 2 right,
3 draw, s skip.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ledger import Ledger
from .rank import CRITERIA, all_pairs, elo, group_ratings

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Ranking &mdash; %(experiment)s</title><style>
:root{color-scheme:dark;--bg:#101314;--fg:#e9ece8;--dim:#7e8a85;--line:#262c2a;--go:#74c3aa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 ui-sans-serif,system-ui,sans-serif}
header{display:flex;justify-content:space-between;align-items:baseline;gap:16px;
  padding:12px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:14px;margin:0;font-weight:600;letter-spacing:-.01em}
.q{color:var(--go);font-size:15px}
.meta{color:var(--dim);font-variant-numeric:tabular-nums;font-size:12px}
main{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:18px 20px}
figure{margin:0;display:flex;flex-direction:column;gap:8px}
video,.ph{width:100%%;aspect-ratio:16/9;background:#000;border:1px solid var(--line);border-radius:3px}
.ph{display:flex;align-items:center;justify-content:center;color:var(--dim);
  font:12px ui-monospace,monospace;text-align:center;padding:20px;white-space:pre-wrap}
figcaption{display:flex;justify-content:space-between;gap:10px;color:var(--dim);
  font:11px ui-monospace,monospace}
button{background:transparent;color:var(--fg);border:1px solid var(--line);
  border-radius:3px;padding:9px;font:inherit;cursor:pointer;width:100%%}
button:hover{border-color:var(--go);color:var(--go)}
footer{padding:0 20px 26px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
footer .hint{color:var(--dim);font:11px ui-monospace,monospace}
.done{padding:60px 20px;text-align:center;color:var(--dim)}
table{border-collapse:collapse;margin:14px auto;font:12px ui-monospace,monospace}
td,th{padding:5px 14px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:400}
</style></head><body>%(body)s
<script>
function vote(w){
  const f=document.getElementById('f');
  document.getElementById('winner').value=w; f.submit();
}
document.addEventListener('keydown',e=>{
  if(!document.getElementById('f'))return;
  if(e.key==='1')vote(document.body.dataset.left);
  if(e.key==='2')vote(document.body.dataset.right);
  if(e.key==='3')vote('');
  if(e.key==='s')vote('skip');
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    ledger: Ledger
    experiment: str
    criterion: str
    root: Path

    def log_message(self, *args) -> None:  # quiet
        pass

    def _send(self, body: str, status: int = 200) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/media/"):
            return self._serve_media(parsed.path[len("/media/"):])
        if parsed.path == "/results":
            return self._send(self._render_results())
        self._send(self._render_pair())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        left = form.get("left", [""])[0]
        right = form.get("right", [""])[0]
        winner = form.get("winner", [""])[0]
        if left and right and winner != "skip":
            self.ledger.record_comparison(
                experiment=self.experiment,
                left_id=left,
                right_id=right,
                winner_id=winner or None,
                criterion=self.criterion,
            )
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def _serve_media(self, rel: str) -> None:
        target = (self.root / rel).resolve()
        if not target.is_file() or self.root.resolve() not in target.parents:
            self.send_error(404)
            return
        data = target.read_bytes()
        kind = "video/mp4" if target.suffix == ".mp4" else "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _state(self) -> tuple[list[str], dict[str, str], set[frozenset[str]]]:
        rows = self.ledger.takes(self.experiment)
        take_ids = [r["take_id"] for r in rows if r["status"] != "failed"]
        paths = {r["take_id"]: (r["path"] or "") for r in rows}
        judged = {
            frozenset((c["left_id"], c["right_id"]))
            for c in self.ledger.comparisons(self.experiment)
            if c["criterion"] == self.criterion
        }
        return take_ids, paths, judged

    def _render_pair(self) -> str:
        take_ids, paths, judged = self._state()
        if len(take_ids) < 2:
            return PAGE % {
                "experiment": self.experiment,
                "body": "<div class='done'>Nothing to rank yet. "
                "Run the experiment first.</div>",
            }

        remaining = [
            p for p in all_pairs(take_ids) if frozenset(p) not in judged
        ]
        total = len(all_pairs(take_ids))
        if not remaining:
            return self._render_results()

        left, right = remaining[0]
        done = total - len(remaining)
        panes = "".join(
            self._pane(t, paths.get(t, ""), n) for n, t in enumerate((left, right), 1)
        )
        body = f"""
<header>
  <h1>{self.experiment}</h1>
  <span class="q">{CRITERIA[self.criterion]}</span>
  <span class="meta">{done} / {total} &middot; <a href="/results"
    style="color:inherit">results</a></span>
</header>
<main>{panes}</main>
<form id="f" method="post">
  <input type="hidden" name="left" value="{left}">
  <input type="hidden" name="right" value="{right}">
  <input type="hidden" name="winner" id="winner" value="">
  <footer>
    <button type="button" onclick="vote('{left}')">1 &nbsp; Left</button>
    <button type="button" onclick="vote('{right}')">2 &nbsp; Right</button>
    <button type="button" onclick="vote('')">3 &nbsp; Draw</button>
    <button type="button" onclick="vote('skip')">s &nbsp; Skip</button>
    <span class="hint">keys 1 / 2 / 3 / s</span>
  </footer>
</form>"""
        return PAGE % {"experiment": self.experiment, "body": body} + (
            f"<script>document.body.dataset.left={json.dumps(left)};"
            f"document.body.dataset.right={json.dumps(right)}</script>"
        )

    def _pane(self, take_id: str, path: str, n: int) -> str:
        rel = ""
        if path:
            try:
                rel = str(Path(path).resolve().relative_to(self.root.resolve()))
            except ValueError:
                rel = ""
        if rel.endswith(".mp4"):
            media = (
                f'<video src="/media/{rel}" autoplay muted loop playsinline></video>'
            )
        elif rel:
            media = (
                f'<div class="ph">dry run &mdash; no video\\n\\n'
                f'<a href="/media/{rel}" style="color:#74c3aa">{rel}</a></div>'
            )
        else:
            media = '<div class="ph">missing</div>'
        # Identity is hidden until after the vote to keep the judgement honest.
        return f"<figure>{media}<figcaption><span>{n}</span></figcaption></figure>"

    def _render_results(self) -> str:
        take_ids, _, _ = self._state()
        triples = [
            (c["left_id"], c["right_id"], c["winner_id"])
            for c in self.ledger.comparisons(self.experiment)
            if c["criterion"] == self.criterion
        ]
        rated = elo(triples, take_ids=take_ids)
        rows = "".join(
            f"<tr><td>{r.take_id}</td><td>{r.rating:.0f}</td>"
            f"<td>{r.wins}&ndash;{r.losses}&ndash;{r.draws}</td></tr>"
            for r in rated
        )
        by_model = group_ratings(rated, "model")
        by_staging = group_ratings(rated, "staging")

        def summary(title: str, data: dict[str, float]) -> str:
            if not data:
                return ""
            body = "".join(f"<tr><td>{k}</td><td>{v:.0f}</td></tr>" for k, v in data.items())
            return f"<h3 style='text-align:center;font-size:13px'>{title}</h3><table>{body}</table>"

        return PAGE % {
            "experiment": self.experiment,
            "body": f"""
<header><h1>{self.experiment} &mdash; results</h1>
<span class="meta">{len(triples)} comparisons &middot;
  <a href="/" style="color:inherit">keep ranking</a></span></header>
<table><tr><th>take</th><th>elo</th><th>w&ndash;l&ndash;d</th></tr>{rows}</table>
{summary("by model", by_model)}
{summary("by staging", by_staging)}""",
        }


def serve(
    ledger: Ledger,
    experiment: str,
    *,
    criterion: str = "overall",
    root: Path | str = "runs",
    port: int = 8765,
) -> None:
    handler = type(
        "BoundHandler",
        (Handler,),
        {
            "ledger": ledger,
            "experiment": experiment,
            "criterion": criterion,
            "root": Path(root),
        },
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"ranking {experiment} ({criterion}) -> http://127.0.0.1:{port}")
    print("keys: 1 left  2 right  3 draw  s skip   ctrl-c to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
