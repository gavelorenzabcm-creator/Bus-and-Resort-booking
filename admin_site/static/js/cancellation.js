(function(){
  'use strict';

  async function fetchAdminStats(){
    const resp = await fetch('/api/admin/stats', { headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' } });
    if(!resp.ok) throw new Error(`stats http ${resp.status}`);
    return resp.json();
  }

  function updateDashboardCounters(stats){
    // Mirrors variables rendered in admin_site/templates/dashboard.html
    const el = (id)=>document.getElementById(id);
    if(!el('total-bookings') || !el('total-customers') || !el('total-revenue') || !el('active-reservations')) return;

    if(typeof stats.total_bookings !== 'undefined') el('total-bookings').textContent = stats.total_bookings || 0;
    if(typeof stats.total_customers !== 'undefined') el('total-customers').textContent = stats.total_customers || 0;
    if(typeof stats.total_revenue !== 'undefined'){
      const fmt = (stats.total_revenue || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      el('total-revenue').textContent = `₱${fmt}`;
    }
    if(typeof stats.active_reservations !== 'undefined') el('active-reservations').textContent = stats.active_reservations || 0;
  }

  async function refreshDashboard(){
    try{
      const stats = await fetchAdminStats();
      updateDashboardCounters(stats);

      // Optionally refresh the booking lists if present.
      // This avoids a full page reload and keeps UI unchanged.
      // For now, we just remove cancelled rows client-side (handled by server response path below).
    }catch(e){
      // Fail silent; cancellation already succeeded.
      console.warn('Dashboard stats refresh failed:', e);
    }
  }

  document.addEventListener('click', async (e)=>{
    const btn = e.target.closest('[data-cancel-booking]');
    if(!btn) return;

    e.preventDefault();

    const url = btn.getAttribute('data-cancel-url');
    const bookingRowSelector = btn.getAttribute('data-row-selector');

    if(!url) return;

    btn.disabled = true;
    btn.dataset.prevText = btn.textContent;
    btn.textContent = 'Cancelling...';

    try{
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
      });

      const data = await resp.json().catch(()=> ({}));

      if(!resp.ok){
        const msg = data && (data.error || data.message) ? (data.error || data.message) : `Cancel failed (${resp.status})`;
        alert(msg);
        return;
      }

      // Remove/hide cancelled row immediately if we can.
      if(bookingRowSelector){
        document.querySelectorAll(bookingRowSelector).forEach(row=>row.remove());
      }

      await refreshDashboard();

      const msg = data.message || 'Booking cancelled successfully.';
      // Non-design change: use a simple alert (since UI design must stay the same).
      alert(msg);
    }catch(err){
      console.error('Cancellation ajax error:', err);
      alert('An unexpected error occurred while cancelling the booking.');
    }finally{
      btn.disabled = false;
      if(btn.dataset.prevText) btn.textContent = btn.dataset.prevText;
    }
  });

})();

