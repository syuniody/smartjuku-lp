/* スマ塾 記事ページの共通スクリプト
   「リンクをコピー」ボタンと、CTAクリックのGA4計測、記事中CTA・追従CTAの差し込み。
   外部ライブラリは使わない。
   X / LINE / Facebook はただのリンクなので、JSが動かなくても機能する。 */

/* 記事中CTAと追従CTA（≤640px）の差し込み。
   記事末のCTA（.article-cta）を持つ記事だけが対象で、一覧ページには何も出ない。
   JSが動かない環境では要素そのものが生まれない（プログレッシブ・エンハンスメント）。
   計測は下のブロックにまとめてある。ここは差し込みと表示条件だけを持つ。 */
(function () {
  'use strict';

  var article = document.querySelector('article');
  var body = document.querySelector('.article-body');
  var endCta = document.querySelector('.article-cta');
  if (!article || !body || !endCta) return;

  // ---- 記事中CTA：本文の最初のh2の直前に1つだけ ----------------------------
  // h2が1つしかない短い記事には入れない。導入を読み終える前に案内が来てしまうため。
  var heads = [];
  Array.prototype.forEach.call(body.children, function (el) {
    if (el.tagName === 'H2') heads.push(el);
  });
  if (heads.length >= 2) {
    var mid = document.createElement('div');
    mid.className = 'article-mid-cta';
    mid.innerHTML =
      '<p>塾のホームページ診断（無料・通常1営業日以内）。' +
      'いま効く改善点を3つ、メールでお送りします。</p>' +
      '<a class="mid-link" href="/#contact">無料HP診断を見る</a>';
    heads[0].parentNode.insertBefore(mid, heads[0]);
  }

  // ---- 追従CTA（≤640px。出す幅の判定はCSSのメディアクエリに任せる） --------
  // 閉じた記事はセッション中もう出さない。キーに記事のパスを入れ、記事ごとに持つ。
  var key = 'sj-article-cta-closed:' + location.pathname;
  try { if (sessionStorage.getItem(key) === '1') return; } catch (e) { /* 使えなくても続行 */ }
  if (!('IntersectionObserver' in window)) return;

  var bar = document.createElement('div');
  bar.className = 'article-mcta';
  bar.innerHTML =
    '<p class="article-mcta-note">塾のHP、改善点3つを無料で</p>' +
    '<a class="article-mcta-btn" href="/#contact">無料診断を見る</a>' +
    '<button class="article-mcta-close" type="button" aria-label="この案内を閉じる">×</button>';
  document.body.appendChild(bar);
  document.body.classList.add('has-article-mcta');

  // 記事の先頭から28%までを覆う目印を置き、それが画面の上へ抜けたら出す。
  // 記事末のCTAが画面に入っている間は引っ込める（同じ案内が二重に出るため）。
  // スクロールごとの計算は足さず、IntersectionObserver だけで判定する。
  var anchor = document.createElement('span');
  anchor.className = 'article-cta-anchor';
  anchor.setAttribute('aria-hidden', 'true');
  article.classList.add('has-cta-anchor');
  article.appendChild(anchor);

  var passed = false, atEnd = false, closed = false;
  function sync() { bar.classList.toggle('is-visible', passed && !atEnd && !closed); }

  new IntersectionObserver(function (es) {
    var e = es[0];
    passed = !e.isIntersecting && e.boundingClientRect.top < 0;
    sync();
  }, { threshold: 0 }).observe(anchor);

  new IntersectionObserver(function (es) {
    atEnd = es[0].isIntersecting;
    sync();
  }, { threshold: 0 }).observe(endCta);

  bar.querySelector('.article-mcta-close').addEventListener('click', function () {
    closed = true;
    sync();
    try { sessionStorage.setItem(key, '1'); } catch (e) { /* 保存できなくても閉じる */ }
    if (typeof window.gtag === 'function') {
      // 閉じた記事のパスだけを送る。個人情報は送らない。
      window.gtag('event', 'article_cta_dismiss', { page_path: location.pathname });
    }
  });
})();

/* CTAクリック計測（GA4）。診断への導線がどこから踏まれたかを article_cta_click で記録する。
   gtagがブロックされている環境では黙って何もしない。 */
(function () {
  'use strict';
  if (typeof window.gtag !== 'function') return;

  var targets = [
    ['.article-cta .btn', 'article_end'],
    ['.article-mid-cta .mid-link', 'mid'],
    ['.article-mcta-btn', 'sticky'],
    ['a.header-cta', 'header'],
    ['.foot-nav a[href="/#contact"]', 'footer']
  ];

  targets.forEach(function (t) {
    Array.prototype.forEach.call(document.querySelectorAll(t[0]), function (el) {
      el.addEventListener('click', function () {
        window.gtag('event', 'article_cta_click', {
          cta_position: t[1],
          page_path: location.pathname
        });
      });
    });
  });
})();

(function () {
  'use strict';

  var buttons = document.querySelectorAll('.sb-copy');
  if (!buttons.length) return;

  function fallbackCopy(text) {
    // クリップボードAPIが使えない環境（http、古いSafari等）向け
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  Array.prototype.forEach.call(buttons, function (btn) {
    var label = btn.querySelector('.sb-text');
    var original = label ? label.textContent : '';

    btn.addEventListener('click', function () {
      var url = btn.getAttribute('data-url') || location.href;

      function done(ok) {
        if (!label) return;
        label.textContent = ok ? 'コピーしました' : 'コピーできませんでした';
        btn.classList.toggle('done', ok);
        setTimeout(function () {
          label.textContent = original;
          btn.classList.remove('done');
        }, 2000);
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { done(true); },
                                                function () { done(fallbackCopy(url)); });
      } else {
        done(fallbackCopy(url));
      }
    });
  });
})();
