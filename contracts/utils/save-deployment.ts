import { HardhatRuntimeEnvironment } from "hardhat/types";
import fs from "node:fs";
import path from "node:path";

export interface DeploymentInfo {
  address: string;
  network: string;
  chainId: string;
  deployer: string;
  blockNumber: number;
  timestamp: number;
  transactionHash?: string;
  constructorArgs?: any[];
}

/**
 * Saves deployment information to a JSON file named ContractName-networkName.json
 */
export async function saveDeploymentInfo(
  contractName: string,
  contractAddress: string,
  hre: HardhatRuntimeEnvironment,
  ethers: any,
  additionalInfo?: {
    transactionHash?: string;
    constructorArgs?: any[];
  }
): Promise<void> {
  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();
  const blockNumber = await ethers.provider.getBlockNumber();
  const block = await ethers.provider.getBlock(blockNumber);

  const networkName = hre.globalOptions.network || "hardhat";

  const deploymentInfo: DeploymentInfo = {
    address: contractAddress,
    network: networkName,
    chainId: network.chainId.toString(),
    deployer: deployer.address,
    blockNumber,
    timestamp: block?.timestamp || Math.floor(Date.now() / 1000),
    ...additionalInfo,
  };

  const deploymentsDir = path.join(process.cwd(), "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const filename = `${contractName}-${networkName}.json`;
  const filepath = path.join(deploymentsDir, filename);

  fs.writeFileSync(filepath, JSON.stringify(deploymentInfo, null, 2));

  console.log(`📝 Deployment info saved to: ${filepath}`);
}

/**
 * Loads deployment information for a specific contract and network
 */
export async function loadDeployment(
  contractName: string,
  networkName: string
): Promise<DeploymentInfo | null> {
  try {
    const filename = `${contractName}-${networkName}.json`;
    const filepath = path.join(process.cwd(), "deployments", filename);

    if (!fs.existsSync(filepath)) {
      return null;
    }

    const data = fs.readFileSync(filepath, "utf-8");
    return JSON.parse(data) as DeploymentInfo;
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
    const deploymentsDir = path.join(process.cwd(), "deployments");

    if (!fs.existsSync(deploymentsDir)) {
      return null;
    }

    const files = fs.readdirSync(deploymentsDir);
    const networkFiles = files.filter(f => f.endsWith(`-${networkName}.json`));

    if (networkFiles.length === 0) {
      return null;
    }

    const deployments: { [contractName: string]: DeploymentInfo } = {};

    for (const file of networkFiles) {
      const contractName = file.replace(`-${networkName}.json`, "");
      const filepath = path.join(deploymentsDir, file);
      const data = fs.readFileSync(filepath, "utf-8");
      deployments[contractName] = JSON.parse(data);
    }

    return deployments;
  } catch (error) {
    return null;
  }
}