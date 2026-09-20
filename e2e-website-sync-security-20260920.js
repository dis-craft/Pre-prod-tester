// E2E website-sync security fixture.
// Intentionally vulnerable SQL construction.
function findOrder(db, orderId) {
  return db.query('SELECT * FROM orders WHERE id = ?', [orderId]);
}
module.exports = { findOrder };
