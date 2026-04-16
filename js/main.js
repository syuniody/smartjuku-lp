/* ==========================================
   SmartJuku LP — main.js
   バニラJS・外部ライブラリ不使用
   ========================================== */

document.addEventListener('DOMContentLoaded', () => {

  /* =========================================
     1. スムーススクロール
     ========================================= */
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const href = anchor.getAttribute('href');
      if (href === '#') return;
      e.preventDefault();
      const target = document.querySelector(href);
      if (!target) return;
      const headerHeight = document.querySelector('.header').offsetHeight;
      const top = target.getBoundingClientRect().top + window.scrollY - headerHeight;
      window.scrollTo({ top, behavior: 'smooth' });
    });
  });

  /* =========================================
     2. ヘッダー背景変化（scroll時）
     ========================================= */
  const header = document.getElementById('header');
  const onScroll = () => {
    if (window.scrollY > 50) {
      header.classList.add('is-scrolled');
    } else {
      header.classList.remove('is-scrolled');
    }
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* =========================================
     3. FAQアコーディオン
     ========================================= */
  document.querySelectorAll('.faq__question').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq__item');
      const isOpen = item.classList.contains('is-open');

      // 他を閉じる
      document.querySelectorAll('.faq__item.is-open').forEach(openItem => {
        openItem.classList.remove('is-open');
        openItem.querySelector('.faq__question').setAttribute('aria-expanded', 'false');
      });

      // トグル
      if (!isOpen) {
        item.classList.add('is-open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
  });

  /* =========================================
     4. スクロールアニメーション（IntersectionObserver）
     ========================================= */
  const animTargets = document.querySelectorAll(
    '.pain__card, .solution__card, .freshness__point, .reasons__card, .steps__card, ' +
    '.demo__template-card, .pricing__card, .faq__item, ' +
    '.profile__inner, .compare__table-wrapper'
  );

  animTargets.forEach(el => el.classList.add('fade-in'));

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    animTargets.forEach(el => observer.observe(el));
  } else {
    // フォールバック：全要素を表示
    animTargets.forEach(el => el.classList.add('is-visible'));
  }

  /* =========================================
     5. フォームバリデーション
     ========================================= */
  const form = document.getElementById('contactForm');
  if (!form) return;

  const showError = (input, message) => {
    input.classList.add('is-error');
    let errorEl = input.parentElement.querySelector('.form-error');
    if (!errorEl) {
      errorEl = document.createElement('p');
      errorEl.className = 'form-error';
      input.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
  };

  const clearError = (input) => {
    input.classList.remove('is-error');
    const errorEl = input.parentElement.querySelector('.form-error');
    if (errorEl) errorEl.remove();
  };

  // リアルタイムクリア
  form.querySelectorAll('.form-input, .form-textarea').forEach(input => {
    input.addEventListener('input', () => clearError(input));
  });

  form.addEventListener('submit', (e) => {
    let isValid = true;

    // 必須チェック
    form.querySelectorAll('[required]').forEach(input => {
      clearError(input);
      if (input.type === 'checkbox') {
        if (!input.checked) {
          isValid = false;
          const mark = input.closest('.form-checkbox');
          if (mark) {
            const wrapper = mark.closest('.form-group');
            let errorEl = wrapper.querySelector('.form-error');
            if (!errorEl) {
              errorEl = document.createElement('p');
              errorEl.className = 'form-error';
              wrapper.appendChild(errorEl);
            }
            errorEl.textContent = 'プライバシーポリシーへの同意が必要です';
          }
        }
        return;
      }
      if (!input.value.trim()) {
        isValid = false;
        showError(input, 'この項目は必須です');
      }
    });

    // メール形式チェック
    const emailInput = form.querySelector('#email');
    if (emailInput && emailInput.value.trim()) {
      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailPattern.test(emailInput.value.trim())) {
        isValid = false;
        showError(emailInput, '正しいメールアドレスを入力してください');
      }
    }

    if (!isValid) {
      e.preventDefault();
      const firstError = form.querySelector('.is-error');
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstError.focus();
      }
      return;
    }

    // Formspree へ AJAX送信
    e.preventDefault();
    const submitBtn = form.querySelector('[type="submit"]');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '送信中…'; }

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { Accept: 'application/json' }
    })
    .then(res => {
      if (res.ok) {
        // Meta Pixel: Lead イベント（コンバージョン計測）
        if (typeof fbq !== 'undefined') { fbq('track', 'Lead'); }

        // サンクスメッセージ表示
        form.innerHTML = [
          '<div class="contact__thanks">',
            '<svg viewBox="0 0 56 56" fill="none" style="width:56px;height:56px;margin-bottom:16px">',
              '<circle cx="28" cy="28" r="28" fill="#FF6B35" opacity="0.12"/>',
              '<path d="M16 28l8 8 16-16" stroke="#FF6B35" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
            '</svg>',
            '<h3>お問い合わせありがとうございます！</h3>',
            '<p>内容を確認のうえ、<strong>1〜2営業日以内</strong>にご連絡いたします。<br>しばらくお待ちください。</p>',
          '</div>'
        ].join('');
      } else {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '無料相談を申し込む'; }
        alert('送信に失敗しました。時間をおいて再度お試しください。');
      }
    })
    .catch(() => {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '無料相談を申し込む'; }
      alert('通信エラーが発生しました。時間をおいて再度お試しください。');
    });
  });

});

/* =========================================
   Admin Carousel
   ========================================= */
(function () {
  const track = document.getElementById('adminTrack');
  if (!track) return;

  const dots = document.querySelectorAll('.admin-carousel__dot');
  const total = track.children.length;
  let current = 0;
  let timer;

  function goTo(idx) {
    current = (idx + total) % total;
    track.style.transform = `translateX(-${current * 100}%)`;
    dots.forEach((d, i) => d.classList.toggle('is-active', i === current));
  }

  function next() { goTo(current + 1); }
  function prev() { goTo(current - 1); }

  function startAuto() {
    timer = setInterval(next, 3500);
  }
  function resetAuto() {
    clearInterval(timer);
    startAuto();
  }

  document.getElementById('adminNext').addEventListener('click', function () { next(); resetAuto(); });
  document.getElementById('adminPrev').addEventListener('click', function () { prev(); resetAuto(); });
  dots.forEach(function (dot) {
    dot.addEventListener('click', function () {
      goTo(parseInt(this.dataset.index));
      resetAuto();
    });
  });

  startAuto();
})();
