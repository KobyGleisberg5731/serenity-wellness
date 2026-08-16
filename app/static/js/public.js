let currentReview = 0;

function getDeviceId() {
  let id = localStorage.getItem('serenity_device_id');
  if (!id) {
    id = 'sd-' + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now());
    localStorage.setItem('serenity_device_id', id);
  }
  document.cookie = `serenity_device_id=${encodeURIComponent(id)};path=/;max-age=31536000;SameSite=Lax`;
  return id;
}

function getDeviceFingerprint() {
  const parts = [
    navigator.userAgent || '',
    navigator.language || '',
    `${screen.width}x${screen.height}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    navigator.platform || '',
    getDeviceId(),
  ];
  return parts.join('|');
}

function deviceHeaders() {
  const id = getDeviceId();
  return { 'X-Device-Id': id };
}

getDeviceId();

function initMobileMenu() {
  const menu = document.getElementById('mobileMenu');
  const toggle = document.getElementById('mobileToggle');
  const closeBtn = document.getElementById('mobileNavClose');
  const backdrop = document.getElementById('mobileMenuBackdrop');
  if (!menu || !toggle) return;

  function openMenu() {
    menu.classList.add('is-open');
    toggle.classList.add('is-open');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Close menu');
    menu.setAttribute('aria-hidden', 'false');
    document.body.classList.add('menu-open');
  }

  function closeMenu() {
    menu.classList.remove('is-open');
    toggle.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open menu');
    menu.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('menu-open');
  }

  toggle.addEventListener('click', () => {
    menu.classList.contains('is-open') ? closeMenu() : openMenu();
  });
  closeBtn?.addEventListener('click', closeMenu);
  backdrop?.addEventListener('click', closeMenu);
  menu.querySelectorAll('.mobile-nav-links a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && menu.classList.contains('is-open')) closeMenu();
  });
  window.closeMobileMenu = closeMenu;
}

initMobileMenu();

function initUtilityMarquee() {
  const bar = document.querySelector('.utility-bar-marquee');
  const track = document.querySelector('[data-marquee]');
  if (!bar || !track) return;

  if (track._marqueeRaf) {
    cancelAnimationFrame(track._marqueeRaf);
    track._marqueeRaf = null;
  }

  const seed = track.querySelector('span');
  const text = (seed?.textContent || '').trim();
  if (!text) return;

  const makeSpan = () => {
    const el = document.createElement('span');
    el.textContent = text;
    return el;
  };

  track.innerHTML = '';
  track.style.transform = 'translate3d(0,0,0)';
  track.appendChild(makeSpan());
  while (track.scrollWidth < bar.clientWidth + 120) {
    track.appendChild(makeSpan());
  }

  const half = track.innerHTML;
  track.innerHTML = half + half;

  const halfWidth = track.scrollWidth / 2;
  if (halfWidth <= 0) return;

  let offset = 0;
  let last = performance.now();
  const speed = 50;

  function tick(now) {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    offset += speed * dt;
    if (offset >= halfWidth) offset -= halfWidth;
    track.style.transform = `translate3d(${-offset}px, 0, 0)`;
    track._marqueeRaf = requestAnimationFrame(tick);
  }

  track.style.animation = 'none';
  track.style.willChange = 'transform';
  track._marqueeRaf = requestAnimationFrame(tick);
}

function scheduleUtilityMarquee() {
  requestAnimationFrame(() => initUtilityMarquee());
}

scheduleUtilityMarquee();
window.addEventListener('resize', scheduleUtilityMarquee);

function initHeroCarousel() {
  const carousel = document.querySelector('[data-hero-carousel]');
  if (!carousel) return;

  if (carousel._heroTimer) {
    clearInterval(carousel._heroTimer);
    carousel._heroTimer = null;
  }

  if (window.matchMedia('(max-width: 768px)').matches) {
    carousel.querySelectorAll('.hero-showcase-slide').forEach((s, i) => {
      s.classList.toggle('active', i === 0);
    });
    return;
  }

  const slides = [...carousel.querySelectorAll('.hero-showcase-slide')];
  if (slides.length < 2) return;

  let idx = slides.findIndex(s => s.classList.contains('active'));
  if (idx < 0) idx = 0;

  const show = (next) => {
    slides[idx].classList.remove('active');
    idx = ((next % slides.length) + slides.length) % slides.length;
    slides[idx].classList.add('active');
  };

  carousel._heroTimer = setInterval(() => show(idx + 1), 4500);
}

requestAnimationFrame(() => initHeroCarousel());
if (!window._heroCarouselResizeBound) {
  window._heroCarouselResizeBound = true;
  window.addEventListener('resize', () => initHeroCarousel());
}

function showReview(n) {

  const slides = document.querySelectorAll('.review-slide');

  if (!slides.length) return;

  slides.forEach(s => s.classList.remove('active'));

  currentReview = ((n % slides.length) + slides.length) % slides.length;

  slides[currentReview].classList.add('active');

}

function nextReview() { showReview(currentReview + 1); }

function prevReview() { showReview(currentReview - 1); }

if (document.querySelector('.review-slide')) {

  setInterval(() => nextReview(), 6000);

}



function openLightbox(src) {

  document.getElementById('lightboxImg').src = src;

  document.getElementById('lightbox').classList.add('open');

}

function closeLightbox() {

  document.getElementById('lightbox').classList.remove('open');

}



if (localStorage.getItem('disclaimer_hidden') !== '1' && document.getElementById('welcomeModal')) {

  document.getElementById('welcomeModal').style.display = 'flex';

}

function closeWelcome() {

  document.getElementById('welcomeModal').style.display = 'none';

  if (document.getElementById('dontShowAgain')?.checked) {

    localStorage.setItem('disclaimer_hidden', '1');

  }

}



/* ── Scroll reveal animations ── */

function initScrollReveal() {

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const els = document.querySelectorAll('.section .container > *, .card, .hero-grid > *');

  els.forEach(el => el.classList.add('reveal'));

  const io = new IntersectionObserver(entries => {

    entries.forEach(entry => {

      if (entry.isIntersecting) {

        entry.target.classList.add('revealed');

        io.unobserve(entry.target);

      }

    });

  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

}

initScrollReveal();



/* ── Multi-step booking modal ── */

const bookingModal = document.getElementById('bookingModal');

const bookingForm = document.getElementById('bookingForm');

const bookingFormStep = document.getElementById('bookingFormStep');

const bookingSuccessStep = document.getElementById('bookingSuccessStep');

const bookingError = document.getElementById('bookingError');

const bookingNextBtn = document.getElementById('bookingNextBtn');

const bookingBackBtn = document.getElementById('bookingBackBtn');

const bookingSubmitBtn = document.getElementById('bookingSubmitBtn');

const bookingLoading = document.getElementById('bookingLoading');

const masseuseStep = document.getElementById('masseuseStep');

const progressMasseuse = document.getElementById('progressMasseuse');

const bookMasseuseId = document.getElementById('bookMasseuseId');

const bookingProgressFill = document.getElementById('bookingProgressFill');



const hasMasseuseStep = masseuseStep && masseuseStep.querySelectorAll('.masseuse-option[data-masseuse-id]:not([data-masseuse-id=""])').length > 0;

let bookingCurrentStep = 1;

const bookingTotalSteps = hasMasseuseStep ? 3 : 2;

const bookingStepMap = hasMasseuseStep ? [1, 2, 3] : [1, 3];



function getLogicalStepIndex(step) {

  return bookingStepMap.indexOf(step);

}



function updateBookingProgress(step) {

  const idx = getLogicalStepIndex(step);

  const pct = bookingTotalSteps <= 1 ? 100 : (idx / (bookingTotalSteps - 1)) * 100;

  if (bookingProgressFill) bookingProgressFill.style.width = `${pct}%`;

  document.querySelectorAll('.booking-progress-step').forEach(el => {

    const s = parseInt(el.dataset.step, 10);

    const sIdx = getLogicalStepIndex(s);

    el.classList.toggle('active', sIdx <= idx);

    el.classList.toggle('current', s === step);

    if (!hasMasseuseStep && s === 2) el.style.display = 'none';

    else el.style.display = '';

  });

}



function showBookingStep(step, direction = 'forward') {

  const panels = document.querySelectorAll('.booking-step-panel');

  panels.forEach(p => {

    const s = parseInt(p.dataset.step, 10);

    if (s === step) {

      p.classList.remove('slide-out-left', 'slide-out-right', 'slide-in-left', 'slide-in-right');

      p.classList.add('active', direction === 'forward' ? 'slide-in-right' : 'slide-in-left');

    } else {

      p.classList.remove('active', 'slide-in-left', 'slide-in-right');

      if (parseInt(p.dataset.step, 10) === bookingCurrentStep) {

        p.classList.add(direction === 'forward' ? 'slide-out-left' : 'slide-out-right');

      }

    }

  });

  bookingCurrentStep = step;

  updateBookingProgress(step);

  const isFirst = getLogicalStepIndex(step) === 0;

  const isLast = getLogicalStepIndex(step) === bookingTotalSteps - 1;

  if (bookingBackBtn) bookingBackBtn.style.display = isFirst ? 'none' : '';

  if (bookingNextBtn) bookingNextBtn.style.display = isLast ? 'none' : '';

  if (bookingSubmitBtn) bookingSubmitBtn.style.display = isLast ? '' : 'none';

}



function todayIsoDate() {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().split('T')[0];
}

function setBookingLoading(on) {
  if (bookingLoading) bookingLoading.hidden = !on;
  [bookingNextBtn, bookingBackBtn, bookingSubmitBtn].forEach(btn => {
    if (btn) btn.disabled = on;
  });
}

function populateBookingSuccess(booking) {
  const emailEl = document.getElementById('successBookingEmail');
  const summaryEl = document.getElementById('successBookingSummary');
  const idEl = document.getElementById('successBookingId');
  if (emailEl) emailEl.textContent = booking.email || '';
  if (idEl) idEl.textContent = booking.booking_id || '';
  if (!summaryEl) return;

  const rows = [
    ['Treatment', booking.service_name],
    ['Session', booking.pricing_label],
    ['Preferred time', booking.preferred_datetime],
    ['Status', 'Pending confirmation'],
  ].filter(([, value]) => value);

  summaryEl.innerHTML = rows.map(([label, value]) => `
    <div class="track-detail-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join('');
}

function initBookingDateTimeFields() {
  const bookDate = document.getElementById('bookDate');
  const bookTime = document.getElementById('bookTime');
  if (bookDate) {
    bookDate.min = todayIsoDate();
    if (!bookDate.value) bookDate.value = bookDate.min;
  }
  if (bookTime && !bookTime.value) bookTime.value = '14:00';
}

function formatBookingDateTime(dateStr, timeStr) {
  const d = new Date(`${dateStr}T${timeStr}`);
  if (Number.isNaN(d.getTime())) return `${dateStr} at ${timeStr}`;
  return d.toLocaleString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

function buildBookingPayload() {
  const data = Object.fromEntries(new FormData(bookingForm));
  const date = (data.preferred_date || '').trim();
  const time = (data.preferred_time || '').trim();
  if (!date || !time) throw new Error('Please select a preferred date and time.');
  data.preferred_datetime = formatBookingDateTime(date, time);
  delete data.preferred_date;
  delete data.preferred_time;
  if (!data.masseuse_id) delete data.masseuse_id;
  data.device_id = getDeviceId();
  data.device_fingerprint = getDeviceFingerprint();
  return data;
}

function resetBookingWizard() {

  bookingCurrentStep = 1;

  setBookingLoading(false);

  if (bookingSuccessStep) {
    bookingSuccessStep.style.display = 'none';
    bookingSuccessStep.classList.remove('success-in');
  }

  const summaryEl = document.getElementById('successBookingSummary');
  if (summaryEl) summaryEl.innerHTML = '';
  const emailEl = document.getElementById('successBookingEmail');
  if (emailEl) emailEl.textContent = '';

  if (bookingForm) bookingForm.reset();

  if (bookMasseuseId) bookMasseuseId.value = '';

  document.querySelectorAll('.masseuse-option').forEach((el, i) => {

    el.classList.toggle('selected', i === 0);

  });

  initBookingDateTimeFields();

  showBookingStep(1);

}



function openBookingModal(opts = {}) {

  if (!bookingModal) return;

  bookingFormStep.style.display = '';

  bookingSuccessStep.style.display = 'none';

  bookingError.style.display = 'none';

  resetBookingWizard();



  const serviceSelect = document.getElementById('bookService');

  const pricingSelect = document.getElementById('bookPricing');

  if (opts.serviceId && serviceSelect) serviceSelect.value = opts.serviceId;

  if (opts.pricingId && pricingSelect) pricingSelect.value = opts.pricingId;

  if (opts.masseuseId && bookMasseuseId) {

    bookMasseuseId.value = opts.masseuseId;

    document.querySelectorAll('.masseuse-option').forEach(el => {

      el.classList.toggle('selected', el.dataset.masseuseId === String(opts.masseuseId));

    });

    if (hasMasseuseStep) showBookingStep(2);

  }



  const subtitle = document.getElementById('bookingModalSubtitle');

  if (subtitle) {

    const parts = [];

    if (opts.serviceName) parts.push(opts.serviceName);

    if (opts.pricingLabel) parts.push(opts.pricingLabel);

    subtitle.textContent = parts.length ? parts.join(' · ') : 'A few quick steps — we\'ll confirm your appointment shortly.';

  }



  bookingModal.style.display = 'flex';

  bookingModal.classList.add('open');

  bookingModal.setAttribute('aria-hidden', 'false');

  document.body.style.overflow = 'hidden';

  requestAnimationFrame(() => bookingModal.querySelector('.booking-card')?.classList.add('entered'));

}



function closeBookingModal() {

  if (!bookingModal) return;

  setBookingLoading(false);

  bookingModal.classList.remove('open');

  bookingModal.querySelector('.booking-card')?.classList.remove('entered');

  setTimeout(() => {

    bookingModal.style.display = 'none';

    bookingModal.setAttribute('aria-hidden', 'true');

  }, 280);

  document.body.style.overflow = '';

}



document.querySelectorAll('[data-book-session]').forEach(btn => {

  btn.addEventListener('click', e => {

    e.preventDefault();

    window.closeMobileMenu?.();

    openBookingModal({

      serviceId: btn.dataset.serviceId || '',

      serviceName: btn.dataset.serviceName || '',

      pricingId: btn.dataset.pricingId || '',

      pricingLabel: btn.dataset.pricingLabel || '',

      masseuseId: btn.dataset.masseuseId || '',

    });

  });

});



document.getElementById('masseusePicker')?.addEventListener('click', e => {

  const btn = e.target.closest('.masseuse-option');

  if (!btn) return;

  document.querySelectorAll('.masseuse-option').forEach(el => el.classList.remove('selected'));

  btn.classList.add('selected');

  if (bookMasseuseId) bookMasseuseId.value = btn.dataset.masseuseId || '';

});



bookingNextBtn?.addEventListener('click', () => {

  bookingError.style.display = 'none';

  const idx = getLogicalStepIndex(bookingCurrentStep);

  if (idx < bookingTotalSteps - 1) {

    showBookingStep(bookingStepMap[idx + 1], 'forward');

  }

});



bookingBackBtn?.addEventListener('click', () => {

  bookingError.style.display = 'none';

  const idx = getLogicalStepIndex(bookingCurrentStep);

  if (idx > 0) {

    showBookingStep(bookingStepMap[idx - 1], 'back');

  }

});



if (bookingForm) {

  bookingForm.addEventListener('submit', async e => {

    e.preventDefault();

    if (getLogicalStepIndex(bookingCurrentStep) < bookingTotalSteps - 1) {

      showBookingStep(bookingStepMap[getLogicalStepIndex(bookingCurrentStep) + 1], 'forward');

      return;

    }



    setBookingLoading(true);

    bookingError.style.display = 'none';

    let data;

    try {

      data = buildBookingPayload();

    } catch (err) {

      bookingError.textContent = err.message;

      bookingError.style.display = 'block';

      setBookingLoading(false);

      return;

    }

    try {

      const res = await fetch('/api/bookings', {

        method: 'POST',

        headers: { 'Content-Type': 'application/json', ...deviceHeaders() },

        body: JSON.stringify(data),

      });

      const json = await res.json();

      if (!res.ok) throw new Error(json.error || 'Booking failed');



      localStorage.setItem('serenity_booking', JSON.stringify({

        booking_id: json.booking.booking_id,

        email: json.booking.email,

      }));

      updateSupportTrackLink();



      populateBookingSuccess(json.booking);

      document.getElementById('successTrackLink').href = json.track_url;

      bookingFormStep.style.display = 'none';

      bookingSuccessStep.style.display = '';

      bookingSuccessStep.classList.add('success-in');

    } catch (err) {

      bookingError.textContent = err.message;

      bookingError.style.display = 'block';

    } finally {

      setBookingLoading(false);

    }

  });

}



bookingModal?.addEventListener('click', e => {

  if (e.target === bookingModal) closeBookingModal();

});



document.addEventListener('keydown', e => {

  if (e.key === 'Escape' && bookingModal?.classList.contains('open')) closeBookingModal();

});



/* ── Support chat widget (non-track pages) ── */
function initSupportChat() {
  if (document.body.classList.contains('page-track')) return;

  const widget = document.getElementById('supportChatWidget');
  const btn = document.getElementById('floatingChat');
  const panel = document.getElementById('supportChatPanel');
  const suggestionsEl = document.getElementById('supportChatSuggestions');
  const thread = document.getElementById('supportChatThread');
  const closeBtn = document.getElementById('supportChatClose');
  if (!widget || !btn || !panel || !suggestionsEl || !thread) return;

  let faqs = [];
  try {
    faqs = JSON.parse(widget.dataset.faqs || '[]');
  } catch (_) {}

  const usedQuestions = new Set();

  function appendBubble(text, role) {
    const div = document.createElement('div');
    div.className = `support-chat-bubble support-chat-${role}`;
    div.innerHTML = `<p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>`;
    thread.appendChild(div);
    thread.scrollTop = thread.scrollHeight;
  }

  function renderSuggestions() {
    const available = faqs.filter(f => !usedQuestions.has(f.question));
    if (!available.length) {
      suggestionsEl.hidden = true;
      suggestionsEl.innerHTML = '';
      return;
    }
    suggestionsEl.hidden = false;
    suggestionsEl.innerHTML = available.map(f => {
      const idx = faqs.indexOf(f);
      return `<button type="button" class="support-suggestion" data-faq-idx="${idx}">${escapeHtml(f.question)}</button>`;
    }).join('');
    suggestionsEl.querySelectorAll('.support-suggestion').forEach(b => {
      b.addEventListener('click', () => pickFaq(Number(b.dataset.faqIdx)));
    });
  }

  function pickFaq(idx) {
    const faq = faqs[idx];
    if (!faq || usedQuestions.has(faq.question)) return;
    usedQuestions.add(faq.question);
    appendBubble(faq.question, 'user');
    window.setTimeout(() => {
      appendBubble(faq.answer, 'bot');
      renderSuggestions();
    }, 300);
    renderSuggestions();
  }

  function openPanel() {
    widget.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    btn.setAttribute('aria-expanded', 'true');
    renderSuggestions();
  }

  function closePanel() {
    widget.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false');
    suggestionsEl.hidden = true;
  }

  btn.addEventListener('click', () => {
    if (widget.classList.contains('open')) closePanel();
    else openPanel();
  });
  closeBtn?.addEventListener('click', closePanel);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && widget.classList.contains('open')) closePanel();
  });

  const trackLink = document.getElementById('supportTrackLink');
  const stored = localStorage.getItem('serenity_booking');
  if (stored && trackLink) {
    try {
      const { booking_id, email } = JSON.parse(stored);
      trackLink.href = `/track?booking_id=${encodeURIComponent(booking_id)}&email=${encodeURIComponent(email)}`;
    } catch (_) {}
  }
}

function updateSupportTrackLink() {
  const trackLink = document.getElementById('supportTrackLink');
  const stored = localStorage.getItem('serenity_booking');
  if (!stored || !trackLink) return;
  try {
    const { booking_id, email } = JSON.parse(stored);
    trackLink.href = `/track?booking_id=${encodeURIComponent(booking_id)}&email=${encodeURIComponent(email)}`;
  } catch (_) {}
}

/* ── Session chat on track page ── */
window.__paymentUiState = window.__paymentUiState || {
  active_crypto_payment: null,
  payment_requests: [],
  booking_status: null,
};

function findCardPayment(messageId) {
  if (!messageId) return null;
  const pr = (window.__paymentUiState?.payment_requests || [])
    .find(p => Number(p.message_id) === Number(messageId));
  return pr?.active_payment || null;
}

function paymentCardFingerprint(pr) {
  const ap = pr.active_payment || {};
  const copy = paymentCardCopy(pr.pay_status === 'open' && ap ? 'pending' : pr.pay_status, ap);
  return [
    pr.message_id,
    pr.pay_status,
    ap.external_id || ap.id || '',
    ap.pay_amount || '',
    ap.status || '',
    copy.button || '',
  ].join(':');
}

function paymentCardStructureFingerprint(pr) {
  const ap = pr.active_payment || {};
  const effectiveStatus = ap && pr.pay_status === 'open' ? 'pending' : pr.pay_status;
  return [pr.message_id, effectiveStatus, ap.external_id || ap.id || '', pr.amount || ''].join(':');
}

function patchPaymentCard(bubble, pr) {
  const ap = pr.active_payment;
  const effectiveStatus = ap && pr.pay_status === 'open' ? 'pending' : pr.pay_status;
  const copy = paymentCardCopy(effectiveStatus, ap);
  const card = bubble.querySelector('[data-pay-card]');
  if (!card) return;

  const nextClass = `chat-pay-card ${copy.cardClass}`.trim();
  if (card.className !== nextClass) card.className = nextClass;

  const eyebrow = card.querySelector('.chat-pay-eyebrow');
  if (eyebrow && eyebrow.textContent !== copy.eyebrow) eyebrow.textContent = copy.eyebrow;

  const hint = card.querySelector('.chat-pay-pending.text-muted');
  if (copy.button && copy.hint) {
    if (hint) {
      if (hint.textContent !== copy.hint) hint.textContent = copy.hint;
    }
  } else if (hint && !copy.button) {
    if (hint.textContent !== copy.hint) hint.textContent = copy.hint;
  }

  const btn = card.querySelector('.chat-pay-btn');
  if (btn && copy.button && btn.textContent !== copy.button) btn.textContent = copy.button;

  if (ap && effectiveStatus === 'pending') {
    const statusLine = bubble.querySelector('.chat-pay-status-line');
    if (statusLine) {
      const status = (ap.status || 'waiting').replace(/_/g, ' ');
      const next = `Status: ${status}`;
      if (statusLine.textContent !== next) statusLine.textContent = next;
    }
  }
}

function paymentCardCopy(payStatus, activePayment) {
  if (payStatus === 'submitted') {
    return {
      eyebrow: 'Payment submitted',
      hint: 'Awaiting confirmation from our team.',
      cardClass: 'chat-pay-card--submitted',
      button: null,
    };
  }
  if (payStatus === 'pending') {
    const cryptoStatus = (activePayment?.status || '').toLowerCase();
    const processing = ['confirming', 'partially_paid', 'sending'].includes(cryptoStatus);
    return {
      eyebrow: processing ? 'Payment detected' : 'Payment in progress',
      hint: processing
        ? 'Your payment is being confirmed on the network.'
        : 'Send your crypto payment to complete checkout.',
      cardClass: 'chat-pay-card--pending',
      button: processing ? 'View payment status' : 'Complete payment',
      payStatus: 'pending',
    };
  }
  return {
    eyebrow: 'Payment required',
    hint: '',
    cardClass: '',
    button: 'Pay now',
    payStatus: 'open',
  };
}

function renderChatMessage(m, activePaymentForMessage = null) {
  const msgType = m.message_type || 'text';
  if (msgType === 'payment_request' && m.meta?.pay_status === 'confirmed') {
    return null;
  }
  const div = document.createElement('div');
  div.className = `chat-bubble chat-${m.sender_type}${msgType === 'payment_request' ? ' chat-payment-request' : ''}`;
  div.dataset.messageType = msgType;
  if (m.id) div.dataset.messageId = String(m.id);
  const time = (m.created_at || '').slice(11, 16);

  if (msgType === 'payment_request') {
    const payStatus = m.meta?.pay_status || 'open';
    const payAmount = m.meta?.amount ?? '';
    const payLabel = m.meta?.amount_label || '';
    const amount = payLabel ? `<p class="chat-pay-amount">${escapeHtml(payLabel)}</p>` : '';
    const activePayment = activePaymentForMessage || m.meta?.active_payment || findCardPayment(m.id) || null;
    const effectiveStatus = activePayment && payStatus === 'open' ? 'pending' : payStatus;
    const copy = paymentCardCopy(effectiveStatus, activePayment);
    let paymentDetail = '';
    if (activePayment && effectiveStatus === 'pending') {
      const cur = (activePayment.pay_currency || '').toUpperCase();
      const sendAmt = activePayment.pay_amount || '';
      if (sendAmt) {
        paymentDetail = `<p class="chat-pay-crypto-line"><strong>Send:</strong> ${escapeHtml(sendAmt)} ${escapeHtml(cur)}</p>`;
      }
      const status = (activePayment.status || 'waiting').replace(/_/g, ' ');
      paymentDetail += `<p class="chat-pay-status-line text-muted">Status: ${escapeHtml(status)}</p>`;
    }
    const payBtn = copy.button
      ? `<button type="button" class="btn btn-sm chat-pay-btn" data-scroll-pay
          data-pay-status="${escapeHtml(copy.payStatus || effectiveStatus)}"
          data-pay-amount="${escapeHtml(String(payAmount))}"
          data-pay-label="${escapeHtml(payLabel)}"
          data-message-id="${escapeHtml(String(m.id || ''))}"
          data-payment-id="${escapeHtml(String(activePayment?.id || activePayment?.external_id || ''))}">${escapeHtml(copy.button)}</button>`
      : `<p class="chat-pay-pending text-muted">${escapeHtml(copy.hint)}</p>`;
    const hint = copy.button && copy.hint
      ? `<p class="chat-pay-pending text-muted">${escapeHtml(copy.hint)}</p>`
      : '';
    div.innerHTML = `
      <div class="chat-pay-card ${copy.cardClass}" data-pay-card>
        <p class="chat-pay-eyebrow">${escapeHtml(copy.eyebrow)}</p>
        <p class="chat-pay-body">${escapeHtml(m.body)}</p>
        ${amount}
        ${paymentDetail}
        ${hint}
        ${payBtn}
      </div>`;
  } else if (msgType === 'payment_proof' && m.attachment_path) {
    const meta = m.sender_type !== 'system'
      ? `<div class="chat-meta">${escapeHtml(m.sender_name)} · ${time}</div>`
      : '';
    div.innerHTML = `${meta}<div class="chat-body">${escapeHtml(m.body)}</div>
      <a class="chat-proof-link" href="/data/${escapeHtml(m.attachment_path)}" target="_blank" rel="noopener">View payment proof</a>`;
  } else {
    const meta = m.sender_type !== 'system'
      ? `<div class="chat-meta">${escapeHtml(m.sender_name)} · ${time}</div>`
      : '';
    div.innerHTML = `${meta}<div class="chat-body">${escapeHtml(m.body)}</div>`;
  }
  return div;
}

function bindChatPayButtons(root = document) {
  root.querySelectorAll('[data-scroll-pay]').forEach(btn => {
    if (btn.dataset.payBound === '1') return;
    btn.dataset.payBound = '1';
    btn.addEventListener('click', () => {
      const amount = parseFloat(btn.dataset.payAmount || '');
      const payStatus = btn.dataset.payStatus || 'open';
      const messageId = btn.dataset.messageId || undefined;
      const cardPayment = findCardPayment(messageId)
        || (window.__paymentUiState?.active_crypto_payments || []).find(p => (
          String(p.id) === String(btn.dataset.paymentId)
          || String(p.external_id) === String(btn.dataset.paymentId)
        ))
        || window.__paymentUiState?.active_crypto_payment;
      if ((payStatus === 'pending' || payStatus === 'submitted') && cardPayment) {
        window.openPaymentModal?.({
          step: 'crypto-active',
          resumePayment: true,
          amount: Number.isFinite(amount) && amount > 0 ? amount : undefined,
          amountLabel: btn.dataset.payLabel || undefined,
          messageId,
          payment: cardPayment,
        });
        return;
      }
      window.openPaymentModal?.({
        step: 'methods',
        amount: Number.isFinite(amount) && amount > 0 ? amount : undefined,
        amountLabel: btn.dataset.payLabel || undefined,
        messageId,
      });
    });
  });
}

function renderPendingPaymentItem(pr) {
  const ap = pr.active_payment;
  const effectiveStatus = ap && pr.pay_status === 'open' ? 'pending' : pr.pay_status;
  const copy = paymentCardCopy(effectiveStatus, ap);
  const btnLabel = copy.button || 'Pay now';
  const paymentId = ap?.id || ap?.external_id || '';
  let statusHint = '';
  if (ap && effectiveStatus === 'pending') {
    const status = (ap.status || 'waiting').replace(/_/g, ' ');
    statusHint = `<p class="pay-pending-status text-muted">Status: ${escapeHtml(status)}</p>`;
  }
  return `
    <div class="pay-pending-item" data-message-id="${escapeHtml(String(pr.message_id || ''))}">
      <div class="pay-pending-copy">
        <p class="pay-pending-eyebrow">${escapeHtml(copy.eyebrow)}</p>
        <p class="pay-pending-desc">${escapeHtml(pr.body || 'Session payment')}</p>
        ${pr.amount_label ? `<p class="pay-pending-amount">${escapeHtml(pr.amount_label)}</p>` : ''}
        ${statusHint}
      </div>
      <button type="button" class="btn btn-sm pay-pending-btn" data-scroll-pay
        data-pay-status="${escapeHtml(copy.payStatus || effectiveStatus)}"
        data-pay-amount="${escapeHtml(String(pr.amount ?? ''))}"
        data-pay-label="${escapeHtml(pr.amount_label || '')}"
        data-message-id="${escapeHtml(String(pr.message_id || ''))}"
        data-payment-id="${escapeHtml(String(paymentId))}">${escapeHtml(btnLabel)}</button>
    </div>`;
}

function updatePayBanner(state) {
  const banner = document.getElementById('pay');
  const list = document.getElementById('payPendingList');
  if (!banner || !list) return;

  let items = (state?.payment_requests || []).filter(
    pr => pr.pay_status === 'open' || pr.pay_status === 'pending'
  );
  const hasOpen = state?.has_open_payments || state?.booking_status === 'payment_pending';
  if (!items.length && hasOpen) {
    items = [{
      message_id: '',
      body: 'Complete payment to confirm your session.',
      amount: state?.amount_due,
      amount_label: state?.amount_label,
      pay_status: state?.active_crypto_payment ? 'pending' : 'open',
      active_payment: state?.active_crypto_payment || null,
    }];
  }
  if (!items.length) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;

  const eyebrow = document.getElementById('payBannerEyebrow');
  const text = document.getElementById('payBannerText');
  const multiple = items.length > 1;
  const anyProcessing = items.some(pr => {
    const status = (pr.active_payment?.status || '').toLowerCase();
    return ['confirming', 'partially_paid', 'sending'].includes(status);
  });
  const anyPending = items.some(pr => pr.active_payment || pr.pay_status === 'pending');

  if (eyebrow) {
    eyebrow.textContent = multiple
      ? 'Payments due'
      : anyProcessing
        ? 'Payment detected'
        : anyPending
          ? 'Payment in progress'
          : 'Payment required';
  }
  if (text) {
    text.textContent = multiple
      ? 'Complete each payment below to confirm your session.'
      : anyProcessing
        ? 'Your crypto payment is being confirmed on the network.'
        : anyPending
          ? 'Complete your crypto payment to confirm your session.'
          : 'Complete payment to confirm your session.';
  }

  list.innerHTML = items.map(renderPendingPaymentItem).join('');
  bindChatPayButtons(list);
}

function updateChatPaymentCards(state, { force = false } = {}) {
  const thread = document.getElementById('chatThread');
  if (!thread) return;
  (state?.payment_requests || []).forEach(pr => {
    const bubble = thread.querySelector(`[data-message-id="${pr.message_id}"]`);
    if (!bubble) return;
    const structureFp = paymentCardStructureFingerprint(pr);
    const fullFp = paymentCardFingerprint(pr);
    if (!force && bubble.dataset.cardStructure === structureFp) {
      bubble.dataset.cardFingerprint = fullFp;
      patchPaymentCard(bubble, pr);
      return;
    }
    const replacement = renderChatMessage({
      id: pr.message_id,
      message_type: 'payment_request',
      sender_type: 'system',
      body: pr.body,
      meta: {
        pay_status: pr.pay_status,
        amount: pr.amount,
        amount_label: pr.amount_label,
        active_payment: pr.active_payment,
      },
    }, pr.active_payment);
    if (!replacement) return;
    replacement.dataset.cardStructure = structureFp;
    replacement.dataset.cardFingerprint = fullFp;
    bubble.replaceWith(replacement);
  });
  bindChatPayButtons(thread);
}

let lastBannerState = '';

function applyPaymentUiState(state, { updateChat = true, updateBanner = true } = {}) {
  if (!state) return;
  window.__paymentUiState = {
    active_crypto_payment: state.active_crypto_payment || null,
    active_crypto_payments: state.active_crypto_payments || [],
    payment_requests: state.payment_requests || [],
    booking_status: state.booking_status || null,
    amount_due: state.amount_due,
    amount_label: state.amount_label,
    has_open_payments: state.has_open_payments,
  };
  if (updateBanner) {
    const bannerFp = `${state.booking_status}|${(state.payment_requests || []).map(pr => paymentCardFingerprint(pr)).join('|')}`;
    if (bannerFp !== lastBannerState) {
      lastBannerState = bannerFp;
      updatePayBanner(state);
    }
  }
  if (updateChat) updateChatPaymentCards(state);
}

async function pollPaymentState(bookingId, email, opts = {}) {
  const { updateChat = true, updateBanner = true } = opts;
  if (!bookingId || !email) return null;
  try {
    const res = await fetch(`/api/bookings/${bookingId}/payment/status?email=${encodeURIComponent(email)}`);
    if (!res.ok) return null;
    const json = await res.json();
    applyPaymentUiState(json, { updateChat, updateBanner });
    if (json.completed) {
      showTrackToast('Payment confirmed', 'Your payment was received. Refreshing your session…', () => {});
      setTimeout(() => window.location.reload(), 1500);
    }
    return json;
  } catch (_) {
    return null;
  }
}

window.applyPaymentUiState = applyPaymentUiState;
window.pollPaymentState = pollPaymentState;

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function showTrackToast(title, body, onClick) {
  const stack = document.getElementById('trackToastStack');
  if (!stack) return;
  const toast = document.createElement('div');
  toast.className = 'track-toast';
  toast.innerHTML = `
    <div class="track-toast-icon">✉</div>
    <div class="track-toast-body">
      <p class="track-toast-title">${escapeHtml(title)}</p>
      <p class="track-toast-text">${escapeHtml(body)}</p>
    </div>
    <button type="button" class="track-toast-close" aria-label="Dismiss">✕</button>
  `;
  const dismiss = () => {
    toast.classList.add('leaving');
    setTimeout(() => toast.remove(), 250);
  };
  toast.querySelector('.track-toast-close').addEventListener('click', e => {
    e.stopPropagation();
    dismiss();
  });
  toast.addEventListener('click', () => {
    dismiss();
    onClick?.();
  });
  stack.appendChild(toast);
  setTimeout(dismiss, 8000);
}

const chatPanel = document.getElementById('sessionChat');
if (chatPanel) {
  const bookingId = chatPanel.dataset.bookingId;
  const email = chatPanel.dataset.email;
  const thread = document.getElementById('chatThread');
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');
  let lastSeenMessageId = Number(window.__bookingChat?.lastMessageId || 0);

  function focusChatInput(prefill = true) {
    chatPanel.classList.add('chat-highlight');
    chatPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
      if (prefill && !chatInput.value.trim()) {
        chatInput.value = 'Hi, I need help with my booking — ';
      }
      chatInput.focus();
      const len = chatInput.value.length;
      chatInput.setSelectionRange(len, len);
      setTimeout(() => chatPanel.classList.remove('chat-highlight'), 1200);
    }, 450);
  }

  let lastMessageCount = thread?.children.length || 0;
  let lastLatestMessageId = Number(thread?.dataset.latestId || window.__bookingChat?.lastMessageId || 0);
  let lastPaymentPatchFp = '';

  function paymentStatePatchFingerprint(state) {
    return (state?.payment_requests || [])
      .map(pr => paymentCardFingerprint(pr))
      .join('|');
  }

  function syncChatThread(messages, notifyAdminReplies = false) {
    let hasNewAdmin = false;
    let latestAdminMsg = null;
    messages.forEach(m => {
      const msgId = Number(m.id || 0);
      if (msgId > lastSeenMessageId && m.sender_type === 'admin') {
        hasNewAdmin = true;
        latestAdminMsg = m;
      }
      lastSeenMessageId = Math.max(lastSeenMessageId, msgId);
    });

    const latestId = messages.reduce((max, m) => Math.max(max, Number(m.id || 0)), 0);
    const visibleCount = messages.filter(m => !(m.message_type === 'payment_request' && m.meta?.pay_status === 'confirmed')).length;
    const shouldRefresh = visibleCount !== lastMessageCount || latestId > lastLatestMessageId;
    if (shouldRefresh) {
      lastMessageCount = visibleCount;
      lastLatestMessageId = latestId;
      thread.dataset.latestId = String(latestId);
      const scrollTop = thread.scrollTop;
      const atBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 48;
      thread.innerHTML = '';
      messages.forEach(m => {
        if (m.message_type === 'payment_request') {
          const pr = (window.__paymentUiState.payment_requests || []).find(
            p => Number(p.message_id) === Number(m.id)
          );
          if (pr) {
            m.meta = {
              ...(m.meta || {}),
              pay_status: pr.pay_status,
              amount: pr.amount ?? m.meta?.amount,
              amount_label: pr.amount_label ?? m.meta?.amount_label,
              active_payment: pr.active_payment,
            };
          }
        }
        const el = renderChatMessage(m);
        if (!el) return;
        if (m.message_type === 'payment_request') {
          const pr = (window.__paymentUiState.payment_requests || []).find(
            p => Number(p.message_id) === Number(m.id)
          );
          if (pr) {
            el.dataset.cardStructure = paymentCardStructureFingerprint(pr);
            el.dataset.cardFingerprint = paymentCardFingerprint(pr);
          }
        }
        thread.appendChild(el);
      });
      bindChatPayButtons(thread);
      if (atBottom) thread.scrollTop = thread.scrollHeight;
      else thread.scrollTop = scrollTop;
      lastPaymentPatchFp = paymentStatePatchFingerprint(window.__paymentUiState);
    } else {
      const patchFp = paymentStatePatchFingerprint(window.__paymentUiState);
      if (patchFp !== lastPaymentPatchFp) {
        lastPaymentPatchFp = patchFp;
        updateChatPaymentCards(window.__paymentUiState);
      }
    }

    if (notifyAdminReplies && hasNewAdmin && latestAdminMsg) {
      showTrackToast(
        `New reply from ${latestAdminMsg.sender_name || 'our team'}`,
        latestAdminMsg.body,
        () => focusChatInput(false)
      );
    }
  }

  function resizeChatInput() {
    if (!chatInput) return;
    chatInput.style.height = 'auto';
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
  }

  chatInput?.addEventListener('input', resizeChatInput);

  chatForm?.addEventListener('submit', async e => {
    e.preventDefault();
    const body = chatInput.value.trim();
    if (!body) return;
    chatInput.disabled = true;
    try {
      const res = await fetch(`/api/bookings/${bookingId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, body }),
      });
      const json = await res.json();
      if (res.ok && json.message) {
        thread.appendChild(renderChatMessage(json.message));
        thread.scrollTop = thread.scrollHeight;
        lastSeenMessageId = Math.max(lastSeenMessageId, Number(json.message.id || 0));
        chatInput.value = '';
        resizeChatInput();
      }
    } finally {
      chatInput.disabled = false;
      chatInput.focus();
    }
  });

  if (thread) {
    thread.scrollTop = thread.scrollHeight;
    bindChatPayButtons(thread);
  }

  async function pollMessages() {
    try {
      const res = await fetch(`/api/bookings/${bookingId}/messages?email=${encodeURIComponent(email)}`);
      if (!res.ok) return;
      const json = await res.json();
      if (json.payment_state) applyPaymentUiState(json.payment_state, { updateChat: false, updateBanner: true });
      syncChatThread(json.messages || [], true);
    } catch (_) {}
  }

  pollMessages();
  setInterval(pollMessages, 10000);

  const helpBtn = document.getElementById('trackHelpBtn');
  if (helpBtn && !sessionStorage.getItem('track_help_dismissed')) {
    setTimeout(() => helpBtn.classList.add('visible'), 5000);
    helpBtn.addEventListener('click', () => {
      helpBtn.classList.remove('visible');
      sessionStorage.setItem('track_help_dismissed', '1');
      focusChatInput(true);
    });
  }
}

/* ── Payment modal on track page ── */
(function initPayPanel() {
  const cfg = window.__bookingChat;
  if (!cfg?.bookingId || !cfg.hasOpenPayments) return;

  const modal = document.getElementById('paymentModal');
  const modalTitle = document.getElementById('paymentModalTitle');
  const modalAmount = document.getElementById('paymentModalAmount');
  const modalBody = document.getElementById('paymentModalBody');
  const stepMethods = document.getElementById('payStepMethods');
  const stepManual = document.getElementById('payStepManual');
  const stepCrypto = document.getElementById('payStepCrypto');
  const methods = cfg.paymentMethods || [];
  const payMethods = document.getElementById('payMethods');
  const payDetailBody = document.getElementById('payDetailBody');
  const payCryptoDetail = document.getElementById('payCryptoDetail');
  const paySubmittedBtn = document.getElementById('paySubmittedBtn');
  const payNote = document.getElementById('payNote');
  const payManualBack = document.getElementById('payManualBack');
  let selectedMethod = null;
  let cryptoPollTimer = null;
  const cryptoState = { step: 'idle', token: '', network: null, payment: null };
  const activePayment = {
    amount: Number(cfg.amountDue || 0),
    amountLabel: cfg.amountLabel || '',
    messageId: null,
  };

  function calcTotal(amount) {
    const fee = Number(cfg.feePercent || 0);
    const base = Number(amount || 0);
    if (fee <= 0) return Math.round(base * 100) / 100;
    return Math.round(base * (1 + fee / 100) * 100) / 100;
  }

  function getActiveAmount() {
    return Number(activePayment.amount || cfg.amountDue || 0);
  }

  function getActiveTotal() {
    return calcTotal(getActiveAmount());
  }

  function setActivePayment(opts = {}) {
    if (opts.amount != null && Number(opts.amount) > 0) {
      activePayment.amount = Number(opts.amount);
      activePayment.amountLabel = opts.amountLabel || formatMoney(activePayment.amount);
    } else {
      activePayment.amount = Number(cfg.amountDue || 0);
      activePayment.amountLabel = cfg.amountLabel || formatMoney(activePayment.amount);
    }
    activePayment.messageId = opts.messageId || null;
    if (modalAmount) modalAmount.textContent = activePayment.amountLabel;
  }

  function setModalStep(step) {
    stepMethods.hidden = step !== 'methods';
    stepManual.hidden = step !== 'manual';
    stepCrypto.hidden = step !== 'crypto';
    modalBody.scrollTop = 0;
  }

  function goToPaymentMethods() {
    stopCryptoPolling();
    cryptoState.payment = null;
    cryptoState.step = 'idle';
    cryptoState.token = '';
    cryptoState.network = null;
    payCryptoDetail.innerHTML = '';
    selectedMethod = null;
    clearSelection();
    modalTitle.textContent = 'Choose how to pay';
    setModalStep('methods');
  }

  window.goToPaymentMethods = goToPaymentMethods;

  function openPaymentModal(opts = 'methods') {
    if (!modal) return;
    if (typeof opts === 'string') opts = { step: opts };
    setActivePayment(opts);
    const step = opts.step || 'methods';
    modal.classList.add('open');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    if (opts.resumePayment && opts.payment) {
      renderCryptoPayment(opts.payment);
      return;
    }
    if (step === 'methods') {
      goToPaymentMethods();
    } else if (step === 'crypto-active' && cryptoState.payment) {
      setModalStep('crypto');
      modalTitle.textContent = 'Send your payment';
    }
  }

  function closePaymentModal() {
    if (!modal) return;
    stopCryptoPolling();
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    setTimeout(() => {
      if (!modal.classList.contains('open')) modal.style.display = 'none';
    }, 280);
    document.body.style.overflow = '';
  }

  window.openPaymentModal = openPaymentModal;
  window.closePaymentModal = closePaymentModal;

  bindChatPayButtons(document.getElementById('payPendingList'));

  document.getElementById('paymentModalClose')?.addEventListener('click', closePaymentModal);
  modal?.addEventListener('click', e => {
    if (e.target === modal) closePaymentModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal?.classList.contains('open')) closePaymentModal();
  });

  payManualBack?.addEventListener('click', goToPaymentMethods);

  function clearSelection() {
    document.querySelectorAll('.pay-method-card').forEach(el => el.classList.remove('active'));
  }

  function formatMoney(n) {
    return `$${Number(n || 0).toFixed(2)}`;
  }

  function cryptoBackButton(targetStep, label = 'Back') {
    return `<button type="button" class="crypto-nav-back crypto-back" data-crypto-step="${targetStep}"><span aria-hidden="true">←</span> ${escapeHtml(label)}</button>`;
  }

  function renderCryptoShell(title, bodyHtml, step, backStep = 'methods', backLabel = 'Methods') {
    cryptoState.step = step;
    modalTitle.textContent = title;
    setModalStep('crypto');
    payCryptoDetail.innerHTML = `
      <div class="crypto-wizard">
        ${cryptoBackButton(backStep, backLabel)}
        <div class="crypto-wizard-body">${bodyHtml}</div>
      </div>`;
    payCryptoDetail.querySelectorAll('.crypto-back').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.cryptoStep;
        if (target === 'tokens') showCryptoTokens();
        else if (target === 'networks') showCryptoNetworks(cryptoState.token);
        else if (target === 'confirm') showCryptoConfirm(cryptoState.network);
        else if (target === 'methods') goToPaymentMethods();
      });
    });
  }

  function showCryptoError(message, backStep = 'networks', backLabel = 'Networks') {
    modalTitle.textContent = 'Payment unavailable';
    setModalStep('crypto');
    payCryptoDetail.innerHTML = `
      <div class="crypto-wizard">
        ${cryptoBackButton(backStep, backLabel)}
        <div class="crypto-error-box">
          <p class="crypto-error-icon" aria-hidden="true">!</p>
          <p class="crypto-error-text">${escapeHtml(message)}</p>
        </div>
        <button type="button" class="btn btn-block crypto-back" data-crypto-step="methods">Choose another method</button>
      </div>`;
    payCryptoDetail.querySelectorAll('.crypto-back').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.cryptoStep;
        if (target === 'networks') showCryptoNetworks(cryptoState.token);
        else if (target === 'methods') goToPaymentMethods();
      });
    });
  }

  async function showCryptoTokens() {
    clearSelection();
    document.querySelector('.pay-method-crypto')?.classList.add('active');
    const res = await fetch('/api/payments/crypto/tokens');
    const json = await res.json();
    const tokens = json.tokens || [];
    if (!tokens.length) {
      showCryptoError(
        json.api_connected === false
          ? 'Crypto payments could not connect to NowPayments. Check your API key in Admin → Payment Methods, or use a manual payment option.'
          : 'No crypto currencies are enabled on your NowPayments account yet.',
        'methods',
        'All methods'
      );
      return;
    }
    const grid = tokens.map(t => `
      <button type="button" class="crypto-choice" data-crypto-token="${escapeHtml(t.code)}">
        <strong>${escapeHtml(t.code)}</strong>
      </button>`).join('');
    renderCryptoShell(
      'Select currency',
      `<p class="crypto-step-note">Total due: <strong>${formatMoney(getActiveTotal())}</strong></p>
       <div class="crypto-choice-grid">${grid}</div>`,
      'tokens',
      'methods',
      'All methods'
    );
    payCryptoDetail.querySelectorAll('[data-crypto-token]').forEach(btn => {
      btn.addEventListener('click', () => showCryptoNetworks(btn.dataset.cryptoToken));
    });
  }

  async function showCryptoNetworks(token) {
    cryptoState.token = token;
    const res = await fetch(`/api/payments/crypto/networks?token=${encodeURIComponent(token)}`);
    const json = await res.json();
    const networks = json.networks || [];
    if (!networks.length) {
      showCryptoError(json.error || `No networks available for ${token}.`, 'tokens', 'Currencies');
      return;
    }
    const grid = networks.map(n => {
      const minLabel = n.min_amount ? `Min ${formatMoney(n.min_amount)}` : '';
      return `
      <button type="button" class="crypto-choice" data-crypto-network="${escapeHtml(n.code)}" data-network-label="${escapeHtml(n.label)}">
        <strong>${escapeHtml(n.label)}</strong>
        <small>${escapeHtml(n.code.toUpperCase())}${minLabel ? ` · ${minLabel}` : ''}</small>
      </button>`;
    }).join('');
    renderCryptoShell(
      `${token} network`,
      `<p class="crypto-step-note">Amount: <strong>${formatMoney(getActiveAmount())}</strong></p>
       <div class="crypto-choice-grid">${grid}</div>`,
      'networks',
      'tokens',
      'Currencies'
    );
    payCryptoDetail.querySelectorAll('[data-crypto-network]').forEach(btn => {
      btn.addEventListener('click', () => {
        cryptoState.network = {
          code: btn.dataset.cryptoNetwork,
          label: btn.dataset.networkLabel,
        };
        showCryptoConfirm(cryptoState.network);
      });
    });
  }

  async function showCryptoConfirm(network) {
    const amount = getActiveAmount();
    const fee = Number(cfg.feePercent || 0);
    let total = getActiveTotal();
    let minWarning = '';
    try {
      const quoteRes = await fetch(
        `/api/bookings/${cfg.bookingId}/payment/crypto/quote?email=${encodeURIComponent(cfg.email)}&amount=${encodeURIComponent(amount)}&pay_currency=${encodeURIComponent(network.code)}`
      );
      const quote = await quoteRes.json();
      if (quote.total) total = Number(quote.total);
      if (quote.below_minimum && quote.min_amount) {
        minWarning = `<p class="crypto-min-warning">Minimum for this network is <strong>${formatMoney(quote.min_amount)}</strong>. Your total is ${formatMoney(total)}.</p>`;
      }
    } catch (_) {}

    const feeAmount = Math.max(0, total - amount);
    const belowMin = minWarning.length > 0;
    renderCryptoShell(
      'Review & pay',
      `<div class="crypto-confirm-box">
        <p><span>Amount</span><strong>${formatMoney(amount)}</strong></p>
        ${fee > 0 ? `<p><span>Fee (${fee}%)</span><strong>${formatMoney(feeAmount)}</strong></p>` : ''}
        <p class="crypto-confirm-total"><span>Total</span><strong>${formatMoney(total)}</strong></p>
        <p><span>Network</span><strong>${escapeHtml(network.label)}</strong></p>
      </div>
      ${minWarning}
      <div class="pay-crypto-actions pay-crypto-actions--stack">
        <button type="button" class="btn btn-block" id="cryptoConfirmPay" ${belowMin ? 'disabled' : ''}>Confirm &amp; pay</button>
      </div>`,
      'confirm',
      'networks',
      'Networks'
    );
    if (!belowMin) {
      document.getElementById('cryptoConfirmPay')?.addEventListener('click', () => createCryptoPayment(network.code));
    }
  }

  function renderCryptoPayment(p) {
    cryptoState.payment = p;
    cryptoState.step = 'payment';
    modalTitle.textContent = 'Send your payment';
    setModalStep('crypto');
    const statusLabel = (p.status || 'waiting').replace(/_/g, ' ');
    payCryptoDetail.innerHTML = `
      <div class="crypto-wizard">
        ${cryptoBackButton('methods', 'Change payment method')}
        <div class="crypto-payment-layout">
          ${p.qr_code ? `<div class="crypto-qr-wrap"><img src="${p.qr_code}" alt="Payment QR code" class="crypto-qr"></div>` : ''}
          <div class="crypto-payment-details">
            <p><strong>Send exactly</strong></p>
            <p class="crypto-send-amount">${escapeHtml(p.pay_amount || '')} ${escapeHtml((p.pay_currency || '').toUpperCase())}</p>
            ${p.pay_address ? `<p class="crypto-wallet-label">Wallet address</p><p class="pay-wallet">${escapeHtml(p.pay_address)}</p>` : ''}
            <p class="crypto-status-line"><span class="crypto-status-pill">${escapeHtml(statusLabel)}</span></p>
            ${p.expires_at ? `<p class="text-muted" style="font-size:0.82rem">Expires: ${escapeHtml(p.expires_at)}</p>` : ''}
            <p class="text-muted" style="font-size:0.82rem;margin-top:0.75rem">We'll confirm automatically once your payment is detected on-chain.</p>
            <div class="pay-crypto-actions pay-crypto-actions--single">
              <button type="button" class="btn btn-sm btn-outline" id="checkCryptoStatus">Check status</button>
              <button type="button" class="btn btn-sm btn-link pay-change-method" id="changePaymentMethod">Change payment method</button>
            </div>
          </div>
        </div>
      </div>`;
    payCryptoDetail.querySelector('.crypto-back')?.addEventListener('click', goToPaymentMethods);
    document.getElementById('changePaymentMethod')?.addEventListener('click', goToPaymentMethods);
    document.getElementById('checkCryptoStatus')?.addEventListener('click', checkCryptoStatus);
    startCryptoPolling();
  }

  async function createCryptoPayment(payCurrency) {
    const btn = document.getElementById('cryptoConfirmPay');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Creating payment…';
    }
    try {
      const res = await fetch(`/api/bookings/${cfg.bookingId}/payment/crypto`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: cfg.email,
          pay_currency: payCurrency,
          amount: getActiveAmount(),
          message_id: activePayment.messageId || undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || 'Could not create crypto payment');
      if (json.payment_state) {
        applyPaymentUiState(json.payment_state);
      } else {
        applyPaymentUiState({
          active_crypto_payment: json.payment,
          active_crypto_payments: [json.payment],
          payment_requests: (window.__paymentUiState?.payment_requests || []).map(pr => {
            if (activePayment.messageId && Number(pr.message_id) === Number(activePayment.messageId)) {
              return { ...pr, pay_status: 'pending', active_payment: json.payment };
            }
            return pr;
          }),
          booking_status: window.__paymentUiState?.booking_status,
          amount_due: getActiveAmount(),
          amount_label: activePayment.amountLabel,
          has_open_payments: true,
        });
      }
      renderCryptoPayment(json.payment);
      pollPaymentState(cfg.bookingId, cfg.email, { updateChat: true, updateBanner: true });
    } catch (err) {
      showCryptoError(err.message, 'networks', 'Networks');
    }
  }

  function stopCryptoPolling() {
    if (cryptoPollTimer) {
      clearInterval(cryptoPollTimer);
      cryptoPollTimer = null;
    }
  }

  function startCryptoPolling() {
    stopCryptoPolling();
    cryptoPollTimer = setInterval(checkCryptoStatus, 30000);
    setTimeout(checkCryptoStatus, 5000);
  }

  async function checkCryptoStatus(silent = false) {
    try {
      const json = await pollPaymentState(cfg.bookingId, cfg.email, { updateChat: false, updateBanner: false });
      if (!json) return;
      if (json.completed) {
        stopCryptoPolling();
        closePaymentModal();
        return;
      }
      const payment = json.payment || json.active_crypto_payment;
      if (payment) {
        cryptoState.payment = payment;
        const statusEl = document.querySelector('.crypto-status-pill');
        if (statusEl) statusEl.textContent = (payment.status || 'waiting').replace(/_/g, ' ');
        if (!silent && payment.status === 'partially_paid') {
          showTrackToast('Partial payment received', 'We detected a partial payment. Please send the remaining amount.', () => {});
        }
      } else if (!silent) {
        alert('No active crypto payment found.');
      }
    } catch (_) {}
  }

  function showMethodDetail(method) {
    stopCryptoPolling();
    selectedMethod = method;
    clearSelection();
    document.querySelector(`[data-method-id="${method.id}"]`)?.classList.add('active');
    modalTitle.textContent = method.name;
    setModalStep('manual');
    const parts = [
      `<p><strong>${escapeHtml(method.name)}</strong></p>`,
      `<p>${escapeHtml(method.instructions || '').replace(/\n/g, '<br>')}</p>`,
    ];
    if (method.wallet_or_handle) {
      parts.push(`<p><span class="pay-wallet">${escapeHtml(method.wallet_or_handle)}</span></p>`);
    }
    if (method.pay_link) {
      parts.push(`<a class="pay-open-link" href="${escapeHtml(method.pay_link)}" target="_blank" rel="noopener">Open payment link →</a>`);
    }
    payDetailBody.innerHTML = parts.join('') + `<p class="pay-proof-hint text-muted" style="font-size:0.82rem;margin-top:0.75rem">After paying, upload proof below so we can confirm your session.</p>`;
  }

  payMethods?.addEventListener('click', e => {
    const cryptoBtn = e.target.closest('[data-pay-action="crypto"]');
    if (cryptoBtn) {
      showCryptoTokens();
      return;
    }
    const card = e.target.closest('[data-method-id]');
    if (!card) return;
    const method = methods.find(m => String(m.id) === card.dataset.methodId);
    if (method) showMethodDetail(method);
  });

  paySubmittedBtn?.addEventListener('click', async () => {
    if (!selectedMethod) {
      alert('Please select a payment method first.');
      return;
    }
    const proofInput = document.getElementById('payProof');
    const proofFile = proofInput?.files?.[0];
    if (!proofFile) {
      alert('Please upload a payment proof screenshot or receipt.');
      return;
    }
    paySubmittedBtn.disabled = true;
    try {
      const formData = new FormData();
      formData.append('email', cfg.email);
      formData.append('method_name', selectedMethod.name);
      formData.append('method_id', selectedMethod.id || '');
      formData.append('note', payNote?.value?.trim() || '');
      formData.append('amount', String(getActiveAmount()));
      if (activePayment.messageId) formData.append('message_id', activePayment.messageId);
      formData.append('proof', proofFile);
      const res = await fetch(`/api/bookings/${cfg.bookingId}/payment/submitted`, {
        method: 'POST',
        body: formData,
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || 'Could not submit payment');
      closePaymentModal();
      showTrackToast('Payment submitted', 'Pending confirmation — we\'ll email you once reviewed.', () => {});
      setTimeout(() => window.location.reload(), 1800);
    } catch (err) {
      alert(err.message);
      paySubmittedBtn.disabled = false;
    }
  });

  if (cfg.activeCryptoPayment) {
    applyPaymentUiState({
      active_crypto_payment: cfg.activeCryptoPayment,
      active_crypto_payments: cfg.activeCryptoPayment ? [cfg.activeCryptoPayment] : [],
      payment_requests: cfg.paymentRequests || [],
      booking_status: cfg.status,
      amount_due: cfg.amountDue,
      amount_label: cfg.amountLabel,
      has_open_payments: cfg.hasOpenPayments,
    });
    pollPaymentState(cfg.bookingId, cfg.email);
  } else if (cfg.paymentRequests?.length) {
    applyPaymentUiState({
      active_crypto_payment: null,
      active_crypto_payments: [],
      payment_requests: cfg.paymentRequests,
      booking_status: cfg.status,
      amount_due: cfg.amountDue,
      amount_label: cfg.amountLabel,
      has_open_payments: cfg.hasOpenPayments,
    });
  }

  if (window.location.hash === '#pay') {
    openPaymentModal({ step: 'methods' });
  }
})();

if (window.__bookingChat?.bookingId) {
  localStorage.setItem('serenity_booking', JSON.stringify({
    booking_id: window.__bookingChat.bookingId,
    email: window.__bookingChat.email,
  }));
  updateSupportTrackLink();
}

initSupportChat();

