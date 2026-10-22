// Cria o utilizador da aplicação com readWrite apenas na base BoardInsight.
// Correr como administrador (a password é pedida no terminal, nunca na linha de comandos):
//   LD_LIBRARY_PATH=/opt/mongodb44/lib /opt/mongodb44/bin/mongo --quiet \
//     -u <admin> --authenticationDatabase admin deploy/mongodb/create-app-user.js
// Depois colocar o mesmo utilizador/password em MONGODB_USERNAME/MONGODB_PASSWORD no .env (600).
const dbName = "BoardInsight";
const user = "boardinsightapp";
const target = db.getSiblingDB(dbName);
if (target.getUser(user)) {
  print(`utilizador ${user} já existe em ${dbName}; roles: ${JSON.stringify(target.getUser(user).roles)}`);
} else {
  target.createUser({ user, pwd: passwordPrompt(), roles: [{ role: "readWrite", db: dbName }] });
  print(`criado ${user} com readWrite em ${dbName}`);
}
