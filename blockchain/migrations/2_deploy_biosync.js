const BioSyncAuth = artifacts.require("BioSyncAuth");

module.exports = function(deployer) {
  deployer.deploy(BioSyncAuth);
};