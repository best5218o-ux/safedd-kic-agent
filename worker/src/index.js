// SAFE-DD 서버 도구 계층(Cloudflare Worker): SEC EDGAR 호출 + 사고 문맥 분류 + 4변수 문장 추출 + 인용 원문 일치 점검
// 규칙 기반(LLM 없음). 공개 API만 사용, 사용자 에이전트 명시, 호출 간격 유지.
const UA = "SAFE-DD research (KIC AI Agent contest) best5218@korea.kr";
const SEC_HDR = { "User-Agent": UA, "Accept-Encoding": "gzip, deflate" };
const INCIDENT = /\b(fire|explosion|explosive|thermal runaway|blaze|wildfire)\b/i;
const PAST = /\b(occurred|ignited|damaged|destroyed|halted|suspended|shut ?down|was extinguished|resulted in|caused|incident|outage)\b/i;
const BOILER = /(could|may|might|risk|hazard|subject to|such as|including|force majeure|acts of god|forward-looking|lease|landlord|tenant)/i;
const VARS = {
  "집중도": /ceasing operations|temporary suspension|all facilities|other battery facilit|offline|suspension of|suspended/i,
  "복구시간": /return to service|returned to service|working towards|resum|restart|repairs/i,
  "보장": /insurance (proceeds|recover)|business interruption|deductible|insurance[^.]{0,80}(received|recognized|settle)/i,
  "귀책·관리": /Administrative Settlement|ASAOC|cause of the fire|OSHA|citation|violation|investigation/i,
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CORS = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS", "access-control-allow-headers": "content-type" };
const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { ...CORS, "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

function decode(s) {
  return s.replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&rsquo;|&lsquo;/g, "'").replace(/&ldquo;|&rdquo;/g, '"');
}
function textOf(html) {
  return decode(html.replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ").replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
}
function classify(t) {
  let best = null;
  for (const s of t.split(/(?<=[.;])\s+/)) {
    if (INCIDENT.test(s)) {
      if (PAST.test(s) && !BOILER.test(s)) return ["incident", s.trim().slice(0, 300)];
      best = best || ["boilerplate", s.trim().slice(0, 200)];
    }
  }
  return best || ["none", ""];
}
function siteKeyword(t, evidence, company) {
  const stop = new Set(["The", "We", "In", "On", "As", "Our", "This", "That", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December", "Company", "Inc", "Corp"]);
  const comp = (company || "").toLowerCase();
  const cands = [...evidence.matchAll(/\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b/g)].map((m) => m[1]).filter((c) => !c.split(" ").some((w) => stop.has(w)) && !comp.includes(c.toLowerCase()));
  let best = null, bc = 0;
  for (const c of new Set(cands)) {
    const n = t.split(c).length - 1;
    if (n > bc) { best = c; bc = n; }
  }
  if (best && bc >= 2) return best;
  const m = evidence.match(/\b(fire|explosion|blaze|wildfire)\b/i);
  return m ? m[1] : "fire";
}
function fourVars(t, site) {
  const out = {}, used = new Set();
  const sents = t.split(/(?<=[.])\s+(?=[A-Z])/);
  const sl = site.toLowerCase();
  for (const [v, pat] of Object.entries(VARS)) {
    let best = null, bs = -1e9;
    for (const s of sents) {
      if (used.has(s) || s.length > 1500) continue;
      const m = pat.exec(s);
      if (!m) continue;
      const near = s.slice(Math.max(0, m.index - 220), m.index + m[0].length + 220).toLowerCase().includes(sl);
      if (!near) continue;
      const score = (/\$\s?\d/.test(s) ? 2 : 0) + (s.toLowerCase().includes(sl) ? 1 : 0) - s.length / 800 + (v === "집중도" && /ceasing operations|suspension of/i.test(s) ? 2.5 : 0) + (v === "보장" && /Martin Lake/i.test(s) ? -3 : 0);
      if (score > bs) { bs = score; best = { s, m }; }
    }
    if (best) {
      const { s, m } = best;
      const a = Math.max(0, m.index - 130), b = Math.min(s.length, m.index + m[0].length + 190);
      let q = s.slice(a, b);
      if (a > 0) q = q.slice(q.indexOf(" ") + 1);
      if (b < s.length) q = q.slice(0, q.lastIndexOf(" "));
      out[v] = q.trim(); used.add(s);
    }
  }
  return out;
}
let tickerCache = null;
async function sec(url, raw) {
  await sleep(150);
  const r = await fetch(url, { headers: SEC_HDR });
  if (!r.ok) throw new Error(`SEC ${r.status}`);
  return raw ? r.text() : r.json();
}
async function handle(req) {
  const u = new URL(req.url);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  const action = u.searchParams.get("action");
  try {
    if (action === "lookup") {
      const q = (u.searchParams.get("q") || "").trim().toLowerCase();
      if (!q) return json({ error: "q 필요" }, 400);
      tickerCache = tickerCache || (await sec("https://www.sec.gov/files/company_tickers.json"));
      const all = Object.values(tickerCache);
      let hit = all.filter((x) => x.ticker.toLowerCase() === q);
      if (!hit.length) hit = all.filter((x) => x.title.toLowerCase().includes(q)).slice(0, 6);
      return json({ results: hit.map((x) => ({ ticker: x.ticker, title: x.title, cik: x.cik_str })) });
    }
    if (action === "filings") {
      const cik = String(parseInt(u.searchParams.get("cik"), 10));
      if (!/^\d+$/.test(cik)) return json({ error: "cik 형식" }, 400);
      const days = Math.min(parseInt(u.searchParams.get("days") || "400", 10), 800);
      const max = Math.min(parseInt(u.searchParams.get("max") || "14", 10), 20);
      const sub = await sec(`https://data.sec.gov/submissions/CIK${cik.padStart(10, "0")}.json`);
      const r = sub.filings.recent, cut = new Date(Date.now() - days * 864e5).toISOString().slice(0, 10), out = [];
      for (let i = 0; i < r.form.length && out.length < max; i++) {
        if (["8-K", "10-Q", "10-K"].includes(r.form[i]) && r.filingDate[i] >= cut)
          out.push({ form: r.form[i], date: r.filingDate[i], acc: r.accessionNumber[i], items: r.items[i], url: `https://www.sec.gov/Archives/edgar/data/${cik}/${r.accessionNumber[i].replace(/-/g, "")}/${r.primaryDocument[i]}` });
      }
      return json({ name: sub.name, cik, filings: out });
    }
    if (action === "analyze") {
      const url = u.searchParams.get("url") || "";
      if (!/^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/\d+\/\d+\/[\w.\-]+$/.test(url)) return json({ error: "허용되지 않는 URL" }, 400);
      const company = u.searchParams.get("company") || "";
      const t = textOf(await sec(url, true));
      const [cls, evidence] = classify(t);
      const res = { url, cls, evidence, chars: t.length };
      if (cls === "incident") {
        const site = siteKeyword(t, evidence, company);
        const vars = fourVars(t, site);
        res.site = site;
        res.vars = Object.fromEntries(Object.entries(vars).map(([k, q]) => [k, { quote: q, substring_in_source: t.includes(q) }]));
        res.evidence_in_source = t.includes(evidence.replace(/\s+/g, " ").trim());
      }
      return json(res);
    }
    return json({ error: "action: lookup | filings | analyze" }, 400);
  } catch (e) {
    return json({ error: String(e.message || e) }, 502);
  }
}

export default { fetch: (req) => handle(req) };
