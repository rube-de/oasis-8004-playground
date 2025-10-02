import { task } from "hardhat/config";
import type { HardhatRuntimeEnvironment } from "hardhat/types";
import { saveDeploymentInfo, loadDeployment, loadNetworkDeployments } from "../utils/save-deployment";

/**
 * Deploy the IdentityRegistry contract
 */
export const deployIdentityRegistry = task("deploy:identity-registry", "Deploy the IdentityRegistry contract")
  .setAction(async () => ({
    default: async (_taskArgs: any, hre: HardhatRuntimeEnvironment) => {
      const { ethers } = await hre.network.connect();
      const networkName = hre.globalOptions.network || "hardhat";

      console.log("\n=== Deploying IdentityRegistry ===");
      console.log("Network:", networkName);

      const [deployer] = await ethers.getSigners();
      console.log("Deployer:", deployer.address);

      const balance = await ethers.provider.getBalance(deployer.address);
      console.log("Account balance:", ethers.formatEther(balance), "ETH");

      // Deploy contract
      const IdentityRegistry = await ethers.getContractFactory("IdentityRegistry");
      console.log("\nDeploying IdentityRegistry...");
      const identityRegistry = await IdentityRegistry.deploy();

      await identityRegistry.waitForDeployment();
      const contractAddress = await identityRegistry.getAddress();

      console.log("IdentityRegistry deployed to:", contractAddress);
      console.log("Transaction hash:", identityRegistry.deploymentTransaction()?.hash);

      // Wait for confirmations
      console.log("Waiting for block confirmations...");
      await identityRegistry.deploymentTransaction()?.wait(2);

      // Save deployment info
      await saveDeploymentInfo(
        "IdentityRegistry",
        contractAddress,
        hre,
        ethers,
        {
          transactionHash: identityRegistry.deploymentTransaction()?.hash,
          constructorArgs: [],
        }
      );

      console.log("\n✅ IdentityRegistry deployment complete!");
      return contractAddress;
    }
  }))
  .build();

/**
 * Deploy the ReputationRegistry contract
 */
export const deployReputationRegistry = task("deploy:reputation-registry", "Deploy the ReputationRegistry contract")
  .addOption({
    name: "identityRegistry",
    description: "Address of the IdentityRegistry contract",
    defaultValue: "",
  })
  .setAction(async () => ({
    default: async (taskArgs: any, hre: HardhatRuntimeEnvironment) => {
      const { ethers } = await hre.network.connect();
      const networkName = hre.globalOptions.network || "hardhat";

      console.log("\n=== Deploying ReputationRegistry ===");
      console.log("Network:", networkName);

      // Get or load IdentityRegistry address
      let identityRegistryAddress = taskArgs.identityRegistry;
      if (!identityRegistryAddress) {
        const deployment = await loadDeployment("IdentityRegistry", networkName);
        if (deployment) {
          identityRegistryAddress = deployment.address;
          console.log("Using deployed IdentityRegistry:", identityRegistryAddress);
        } else {
          throw new Error(
            "IdentityRegistry address not provided and no deployment found. " +
            "Deploy IdentityRegistry first or provide --identity-registry address"
          );
        }
      }

      const [deployer] = await ethers.getSigners();
      console.log("Deployer:", deployer.address);

      const balance = await ethers.provider.getBalance(deployer.address);
      console.log("Account balance:", ethers.formatEther(balance), "ETH");

      // Deploy contract
      const ReputationRegistry = await ethers.getContractFactory("ReputationRegistry");
      console.log("\nDeploying ReputationRegistry...");
      console.log("Constructor args:");
      console.log("  IdentityRegistry:", identityRegistryAddress);

      const reputationRegistry = await ReputationRegistry.deploy(identityRegistryAddress);

      await reputationRegistry.waitForDeployment();
      const contractAddress = await reputationRegistry.getAddress();

      console.log("ReputationRegistry deployed to:", contractAddress);
      console.log("Transaction hash:", reputationRegistry.deploymentTransaction()?.hash);

      // Wait for confirmations
      console.log("Waiting for block confirmations...");
      await reputationRegistry.deploymentTransaction()?.wait(2);

      // Save deployment info
      await saveDeploymentInfo(
        "ReputationRegistry",
        contractAddress,
        hre,
        ethers,
        {
          transactionHash: reputationRegistry.deploymentTransaction()?.hash,
          constructorArgs: [identityRegistryAddress],
        }
      );

      console.log("\n✅ ReputationRegistry deployment complete!");
      return contractAddress;
    }
  }))
  .build();

/**
 * Deploy the ValidationRegistry contract
 */
export const deployValidationRegistry = task("deploy:validation-registry", "Deploy the ValidationRegistry contract")
  .addOption({
    name: "identityRegistry",
    description: "Address of the IdentityRegistry contract",
    defaultValue: "",
  })
  .setAction(async () => ({
    default: async (taskArgs: any, hre: HardhatRuntimeEnvironment) => {
      const { ethers } = await hre.network.connect();
      const networkName = hre.globalOptions.network || "hardhat";

      console.log("\n=== Deploying ValidationRegistry ===");
      console.log("Network:", networkName);

      // Get or load IdentityRegistry address
      let identityRegistryAddress = taskArgs.identityRegistry;
      if (!identityRegistryAddress) {
        const deployment = await loadDeployment("IdentityRegistry", networkName);
        if (deployment) {
          identityRegistryAddress = deployment.address;
          console.log("Using deployed IdentityRegistry:", identityRegistryAddress);
        } else {
          throw new Error(
            "IdentityRegistry address not provided and no deployment found. " +
            "Deploy IdentityRegistry first or provide --identity-registry address"
          );
        }
      }

      const [deployer] = await ethers.getSigners();
      console.log("Deployer:", deployer.address);

      const balance = await ethers.provider.getBalance(deployer.address);
      console.log("Account balance:", ethers.formatEther(balance), "ETH");

      // Deploy contract
      const ValidationRegistry = await ethers.getContractFactory("ValidationRegistry");
      console.log("\nDeploying ValidationRegistry...");
      console.log("Constructor args:");
      console.log("  IdentityRegistry:", identityRegistryAddress);

      const validationRegistry = await ValidationRegistry.deploy(identityRegistryAddress);

      await validationRegistry.waitForDeployment();
      const contractAddress = await validationRegistry.getAddress();

      console.log("ValidationRegistry deployed to:", contractAddress);
      console.log("Transaction hash:", validationRegistry.deploymentTransaction()?.hash);

      // Wait for confirmations
      console.log("Waiting for block confirmations...");
      await validationRegistry.deploymentTransaction()?.wait(2);

      // Get and display expiration slots
      const expirationSlots = await validationRegistry.getExpirationSlots();
      console.log("Validation expiration slots:", expirationSlots.toString());

      // Save deployment info
      await saveDeploymentInfo(
        "ValidationRegistry",
        contractAddress,
        hre,
        ethers,
        {
          transactionHash: validationRegistry.deploymentTransaction()?.hash,
          constructorArgs: [identityRegistryAddress],
        }
      );

      console.log("\n✅ ValidationRegistry deployment complete!");
      return contractAddress;
    }
  }))
  .build();

/**
 * Deploy all three registry contracts in the correct order
 */
export const deployAllRegistries = task("deploy:all-registries", "Deploy all ERC-8004 registry contracts")
  .setAction(async () => ({
    default: async (_taskArgs: any, hre: HardhatRuntimeEnvironment) => {
      console.log("\n========================================");
      console.log("  ERC-8004 Registry Deployment");
      console.log("========================================");

      const networkName = hre.globalOptions.network || "hardhat";
      console.log("\nTarget Network:", networkName);

      const { ethers } = await hre.network.connect();
      const [deployer] = await ethers.getSigners();
      const balance = await ethers.provider.getBalance(deployer.address);

      console.log("Deployer Address:", deployer.address);
      console.log("Deployer Balance:", ethers.formatEther(balance), "ETH");

      if (balance === BigInt(0)) {
        throw new Error("Deployer account has no ETH balance!");
      }

      // Deploy contracts in order
      console.log("\n🚀 Starting deployment sequence...\n");

      // 1. Deploy IdentityRegistry
      console.log("Step 1/3: IdentityRegistry");
      const identityRegistryAddress = await hre.tasks.getTask("deploy:identity-registry").run({});

      // 2. Deploy ReputationRegistry
      console.log("\nStep 2/3: ReputationRegistry");
      const reputationRegistryAddress = await hre.tasks.getTask("deploy:reputation-registry").run({
        identityRegistry: identityRegistryAddress,
      });

      // 3. Deploy ValidationRegistry
      console.log("\nStep 3/3: ValidationRegistry");
      const validationRegistryAddress = await hre.tasks.getTask("deploy:validation-registry").run({
        identityRegistry: identityRegistryAddress,
      });

      // Print deployment summary
      console.log("\n========================================");
      console.log("  Deployment Summary");
      console.log("========================================");
      console.log("Network:", networkName);
      console.log("Deployer:", deployer.address);
      console.log("\n📋 Deployed Contracts:");
      console.log("  IdentityRegistry:  ", identityRegistryAddress);
      console.log("  ReputationRegistry:", reputationRegistryAddress);
      console.log("  ValidationRegistry:", validationRegistryAddress);
      console.log("\n✅ All registries deployed successfully!");
      console.log("========================================\n");

      return {
        identityRegistry: identityRegistryAddress,
        reputationRegistry: reputationRegistryAddress,
        validationRegistry: validationRegistryAddress,
      };
    }
  }))
  .build();

/**
 * Get deployed registry addresses for a network
 */
export const getRegistries = task("get:registries", "Get deployed registry addresses for the current network")
  .setAction(async () => ({
    default: async (_taskArgs: any, hre: HardhatRuntimeEnvironment) => {
      const networkName = hre.globalOptions.network || "hardhat";
      console.log("\n=== Registry Addresses ===");
      console.log("Network:", networkName);

      const deployments = await loadNetworkDeployments(networkName);

      if (!deployments) {
        console.log("\n❌ No deployments found for network:", networkName);
        return;
      }

      console.log("\n📋 Deployed Contracts:");

      const registries = ["IdentityRegistry", "ReputationRegistry", "ValidationRegistry"];

      for (const registry of registries) {
        if (deployments[registry]) {
          console.log(`\n${registry}:`);
          console.log("  Address:", deployments[registry].address);
          console.log("  Block:", deployments[registry].blockNumber);
          console.log("  Deployer:", deployments[registry].deployer);
        }
      }

      console.log("\n==========================\n");
      return deployments;
    }
  }))
  .build();

