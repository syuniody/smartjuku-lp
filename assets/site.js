/* スマ塾 記事ページの共通スクリプト
   「リンクをコピー」ボタンと、CTAクリックのGA4計測。外部ライブラリは使わない。
   X / LINE / Facebook はただのリンクなので、JSが動かなくても機能する。 */

/* CTAクリック計測（GA4）。診断への導線がどこから踏まれたかを article_cta_click で記録する。
   gtagがブロックされている環境では黙って何もしない。 */
(function () {
  'use strict';
  if (typeof window.gtag !== 'function') return;

  var targets = [
    ['.article-cta .btn', 'article_end'],
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
