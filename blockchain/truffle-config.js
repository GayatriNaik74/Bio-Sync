/**
 * BioSync — Truffle Configuration
 * Connects to local Ganache Desktop instance
 */
module.exports = {
  networks: {
    development: {
      host:    "127.0.0.1",  // Ganache default host
      port:    7545,           // Ganache default port
      network_id: "*"         // match any network ID
    }
  },
  compilers: {
    solc: {
      version: "0.8.19"      // Solidity compiler version
    }
  }
};