/* The background's cover and crop use the visible area below the real navbar. */
(function () {
    'use strict';
    const nav = document.querySelector('.topnav');
    const backdrop = document.querySelector('.photo-backdrop');
    function updateBackgroundBounds() {
        const top = Math.max(0, nav.getBoundingClientRect().bottom);
        backdrop.style.setProperty('--photo-top', top + 'px');
    }
    updateBackgroundBounds();
    new ResizeObserver(updateBackgroundBounds).observe(nav);
    window.addEventListener('scroll', updateBackgroundBounds, { passive: true });
    window.addEventListener('resize', updateBackgroundBounds);
}());
