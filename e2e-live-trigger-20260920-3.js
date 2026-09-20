// Fresh SQL injection fixture for the canonical pre-prod pipeline.
function getAccount(db, username) {
  const query = `SELECT * FROM accounts WHERE username = '${username}'`;
  return db.query(query);
}
module.exports = { getAccount };
