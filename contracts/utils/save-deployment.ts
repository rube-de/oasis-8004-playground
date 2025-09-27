import { HardhatRuntimeEnvironment } from "hardhat/types";
import { ethers } from "ethers";
import fs from "fs/promises";
import path from "path";

interface DeploymentInfo {
  address: string;
  transactionHash?: string;
  blockNumber: number;
  timestamp: number;
  deployer: string;
  network: string;
  chainId: bigint;
  constructorArgs?: any[];
}

interface DeploymentRegistry {
  [network: string]: {
    [contractName: string]: DeploymentInfo;
  };
}

const DEPLOYMENTS_DIR = "deployments";
const DEPLOYMENTS_FILE = "deployments.json";

/**
 * Saves deployment information to a JSON file organized by network and contract name
 */
export async function saveDeploymentInfo(
  contractName: string,
  contractAddress: string,
  hre: HardhatRuntimeEnvironment,
  ethersProvider: any,
  additionalInfo?: {
    transactionHash?: string;
    constructorArgs?: any[];
  }
): Promise<void> {
  try {
    const networkName = hre.globalOptions.network || "hardhat";
    const [deployer] = await ethersProvider.getSigners();
    const blockNumber = await ethersProvider.provider.getBlockNumber();
    const block = await ethersProvider.provider.getBlock(blockNumber);
    const network = await ethersProvider.provider.getNetwork();

    const deploymentInfo: DeploymentInfo = {
      address: contractAddress,
      transactionHash: additionalInfo?.transactionHash,
      blockNumber,
      timestamp: block?.timestamp || Date.now() / 1000,
      deployer: deployer.address,
      network: networkName,
      chainId: network.chainId,
      constructorArgs: additionalInfo?.constructorArgs || [],
    };

    // Create deployments directory if it doesn't exist
    const deploymentsPath = path.join(process.cwd(), DEPLOYMENTS_DIR);
    await fs.mkdir(deploymentsPath, { recursive: true });

    // Load existing deployments or create new registry
    const deploymentsFile = path.join(deploymentsPath, DEPLOYMENTS_FILE);
    let registry: DeploymentRegistry = {};

    try {
      const existingData = await fs.readFile(deploymentsFile, "utf-8");
      registry = JSON.parse(existingData);
    } catch (error) {
      // File doesn't exist or is invalid, start fresh
      registry = {};
    }

    // Update registry with new deployment
    if (!registry[networkName]) {
      registry[networkName] = {};
    }
    registry[networkName][contractName] = deploymentInfo;

    // Save updated registry
    await fs.writeFile(
      deploymentsFile,
      JSON.stringify(registry, (key, value) =>
        typeof value === "bigint" ? value.toString() : value,
        2
      )
    );

    // Also save individual deployment file for this network
    const networkDeploymentFile = path.join(deploymentsPath, `${networkName}.json`);
    await fs.writeFile(
      networkDeploymentFile,
      JSON.stringify(
        registry[networkName],
        (key, value) => (typeof value === "bigint" ? value.toString() : value),
        2
      )
    );

    console.log(`\n📝 Deployment info saved to ${deploymentsFile}`);
  } catch (error) {
    console.error("Failed to save deployment info:", error);
  }
}

/**
 * Loads deployment information for a specific contract and network
 */
export async function loadDeployment(
  contractName: string,
  networkName: string
): Promise<DeploymentInfo | null> {
  try {
    const deploymentsFile = path.join(process.cwd(), DEPLOYMENTS_DIR, DEPLOYMENTS_FILE);
    const data = await fs.readFile(deploymentsFile, "utf-8");
    const registry: DeploymentRegistry = JSON.parse(data);

    return registry[networkName]?.[contractName] || null;
  } catch (error) {
    return null;
  }
}

/**
 * Loads all deployments for a specific network
 */
export async function loadNetworkDeployments(
  networkName: string
): Promise<{ [contractName: string]: DeploymentInfo } | null> {
  try {
    const deploymentsFile = path.join(process.cwd(), DEPLOYMENTS_DIR, DEPLOYMENTS_FILE);
    const data = await fs.readFile(deploymentsFile, "utf-8");
    const registry: DeploymentRegistry = JSON.parse(data);

    return registry[networkName] || null;
  } catch (error) {
    return null;
  }
}