// Fresh E2E security fixture: intentionally vulnerable SQL construction.
function lookupUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`;
  return db.query(query);
}
module.exports = { lookupUser };
