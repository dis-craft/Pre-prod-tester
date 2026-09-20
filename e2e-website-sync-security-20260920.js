// E2E website-sync security fixture.
// Intentionally vulnerable SQL construction.
function findOrder(db, orderId) {
  const sql = `SELECT * FROM orders WHERE id = '${orderId}'`;
  return db.query(sql);
}
module.exports = { findOrder };
