/* X numbers reader (bookmarklet).
   Run on your own profile page (x.com/yourname) while signed in. It scrolls
   your recent posts, reads the numbers X shows under each one plus your
   follower count, and opens the Control Panel to review and save them.
   It reads only what is on screen; it never posts, likes or follows.
   The Control Panel turns this file into the bookmark, filling in its own address.
   Use block comments only: the code becomes a single javascript: URL. */
(async () => {
  const PANEL = "__PANEL__";
  const host = location.hostname.replace(/^(www|mobile)\./, "");
  const m = location.pathname.match(/^\/([A-Za-z0-9_]{1,15})\/?$/);
  if (!["x.com", "twitter.com"].includes(host) || !m || ["home", "explore", "notifications", "messages", "i", "settings", "search"].includes(m[1].toLowerCase())) {
    alert("Open your X profile page first (x.com/yourname), then tap this bookmark again.");
    return;
  }
  const handle = m[1];
  const toNum = (s) => {
    const k = String(s || "").replace(/,/g, "").trim().match(/^([\d.]+)\s*([KkMm]?)/);
    if (!k) return 0;
    return Math.round(parseFloat(k[1]) * (/k/i.test(k[2]) ? 1e3 : /m/i.test(k[2]) ? 1e6 : 1));
  };
  const box = document.createElement("div");
  box.style.cssText = "position:fixed;z-index:2147483647;left:50%;top:16px;transform:translateX(-50%);background:#15222B;color:#fff;font:15px/1.4 system-ui,sans-serif;padding:14px 18px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.3);max-width:90vw;text-align:center";
  box.textContent = "Reading your posts… keep this tab open.";
  document.body.appendChild(box);

  const posts = new Map();
  const grab = () => {
    document.querySelectorAll('article[data-testid="tweet"]').forEach((a) => {
      const link = [...a.querySelectorAll('a[href*="/status/"]')].find((x) => x.querySelector("time"));
      if (!link) return;
      const mm = (link.getAttribute("href") || "").match(/^\/([^/]+)\/status\/(\d+)/);
      if (!mm || mm[1].toLowerCase() !== handle.toLowerCase()) return; /* skip other people's posts you reposted */
      const group = a.querySelector('[role="group"][aria-label]');
      const label = group ? group.getAttribute("aria-label") : "";
      const pick = (word) => { const r = label.match(new RegExp("([\\d,.]+[KkMm]?)\\s+" + word, "i")); return r ? toNum(r[1]) : 0; };
      let views = pick("views?");
      if (!views) {
        const v = a.querySelector('a[href$="/analytics"]');
        const r = v && (v.getAttribute("aria-label") || v.textContent).match(/[\d,.]+[KkMm]?/);
        if (r) views = toNum(r[0]);
      }
      const t = a.querySelector('[data-testid="tweetText"]');
      posts.set(mm[2], {
        id: mm[2],
        time: link.querySelector("time").getAttribute("datetime"),
        text: t ? t.innerText.replace(/\s+/g, " ").slice(0, 120) : "",
        views, likes: pick("likes?"), replies: pick("repl(?:y|ies)"), reposts: pick("reposts?"), bookmarks: pick("bookmarks?"),
      });
    });
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 14; i++) {
    grab();
    box.textContent = `Reading your posts… ${posts.size} found. Keep this tab open.`;
    window.scrollBy(0, Math.round(window.innerHeight * 0.85));
    await sleep(1300);
  }
  grab();
  window.scrollTo(0, 0);

  const fl = document.querySelector(`a[href="/${handle}/verified_followers"], a[href="/${handle}/followers"]`);
  const followers = fl ? toNum(fl.textContent) : 0;
  const data = { v: 1, handle, followers, at: new Date().toISOString(), posts: [...posts.values()] };
  const payload = btoa(unescape(encodeURIComponent(JSON.stringify(data))));
  const url = PANEL + "#import=" + encodeURIComponent(payload);

  box.textContent = "";
  const msg = document.createElement("div");
  msg.textContent = `Found ${posts.size} posts` + (followers ? ` and ${followers.toLocaleString()} followers.` : ".");
  const btn = document.createElement("a");
  btn.href = url; btn.target = "_blank"; btn.rel = "noopener";
  btn.textContent = "Review and save in Control Panel";
  btn.style.cssText = "display:inline-block;margin-top:10px;background:#3DC29A;color:#06231A;font-weight:600;padding:8px 14px;border-radius:8px;text-decoration:none";
  const close = document.createElement("button");
  close.textContent = "Close";
  close.style.cssText = "margin:10px 0 0 8px;background:transparent;color:#fff;border:1px solid #fff;border-radius:8px;padding:7px 12px;font:inherit;cursor:pointer";
  close.onclick = () => box.remove();
  box.append(msg, btn, close);
  if (!posts.size) msg.textContent = "No posts found. Make sure you're on your profile's Posts tab and signed in, then try again.";
})();
