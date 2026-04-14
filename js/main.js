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
      // 最初のエラーにスクロール
      const firstError = form.querySelector('.is-error');
      if (firstError) {
        firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstError.focus();
      }
    }
    // action が空の場合は送信を止める（プレースホルダー状態）
    if (!form.action || form.action === window.location.href) {
      e.preventDefault();
      if (isValid) {
        alert('お問い合わせありがとうございます。\n（※現在テスト表示です。フォーム送信先は未設定です。）');
      }
    }
  });

});
