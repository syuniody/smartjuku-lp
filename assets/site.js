/* スマ塾 記事ページの共通スクリプト
   いまのところ「リンクをコピー」ボタンだけ。外部ライブラリは使わない。
   X / LINE / Facebook はただのリンクなので、JSが動かなくても機能する。 */
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
