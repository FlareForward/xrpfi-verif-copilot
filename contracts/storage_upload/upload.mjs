/**
 * 0G Storage upload helper for XRPFi Verifiable Copilot.
 *
 * Usage:
 *   node upload.mjs <json_file> <private_key>
 *
 * Outputs JSON: { "root_hash": "0x...", "tx_hash": "0x...", "explorer_url": "..." }
 *
 * 0G mainnet defaults. Override with ZERO_G_RPC_URL, ZERO_G_STORAGE_URL, ZERO_G_EXPLORER.
 */

import {
  calculatePrice,
  getFlowContract,
  getMarketContract,
  Indexer,
  Uploader,
  ZgFile,
} from "@0glabs/0g-ts-sdk";
import { ethers } from "ethers";
import path from "path";

const EVM_RPC = process.env.ZERO_G_RPC_URL || "https://0g-rpc.publicnode.com";
const INDEXER = process.env.ZERO_G_STORAGE_URL || "https://indexer-storage-turbo.0g.ai";
const EXPLORER = process.env.ZERO_G_EXPLORER || "https://chainscan.0g.ai";
const EXPECTED_CHAIN_ID = BigInt(process.env.ZERO_G_CHAIN_ID || "16661");
const FLOW_CONTRACT = process.env.ZERO_G_FLOW_CONTRACT
  || "0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526";
const UPLOAD_TAGS = "0x";

async function estimateStorageFee(file, flow, provider) {
  const [submission, submissionErr] = await file.createSubmission(UPLOAD_TAGS);
  if (submissionErr || !submission) {
    throw new Error(`Submission error: ${submissionErr || "empty submission"}`);
  }

  const marketAddress = await flow.market();
  const market = getMarketContract(marketAddress, provider);
  const pricePerSector = await market.pricePerSector();
  const fee = calculatePrice(submission, pricePerSector);
  if (fee <= 0n) {
    throw new Error(
      `Calculated non-positive 0G storage fee ${fee} from market ${marketAddress}`,
    );
  }

  return { fee, marketAddress, pricePerSector };
}

async function upload(filePath, privateKey) {
  // Provider + signer
  const provider = new ethers.JsonRpcProvider(EVM_RPC);
  const signer = new ethers.Wallet(privateKey, provider);

  const network = await provider.getNetwork();
  if (network.chainId !== EXPECTED_CHAIN_ID) {
    throw new Error(
      `0G chain mismatch: RPC ${EVM_RPC} returned ${network.chainId}, expected ${EXPECTED_CHAIN_ID}`,
    );
  }

  const balance = await provider.getBalance(signer.address);
  if (balance === 0n) {
    throw new Error(`No OG balance at ${signer.address} on chain ${network.chainId}`);
  }

  const file = await ZgFile.fromFilePath(filePath);
  try {
    const [tree, treeErr] = await file.merkleTree();
    if (treeErr) throw new Error(`Merkle tree error: ${treeErr}`);

    const rootHash = tree.rootHash();

    // Upload via indexer, but pin the mainnet Flow contract explicitly. Some
    // storage nodes can report stale Galileo/testnet flow addresses in status.
    const indexer = new Indexer(INDEXER);
    const [clients, nodeErr] = await indexer.selectNodes(1);
    if (nodeErr) throw new Error(`Node selection error: ${nodeErr}`);

    const flow = getFlowContract(FLOW_CONTRACT, signer);
    const { fee, marketAddress, pricePerSector } = await estimateStorageFee(
      file,
      flow,
      provider,
    );
    const uploader = new Uploader(clients, EVM_RPC, flow);
    const [uploadResult, uploadErr] = await uploader.uploadFile(file, {
      tags: UPLOAD_TAGS,
      finalityRequired: true,
      taskSize: 10,
      expectedReplica: 1,
      skipTx: false,
      fee,
    });
    if (uploadErr) throw new Error(`Upload error: ${uploadErr}`);

    const txHash = typeof uploadResult === "string" ? uploadResult : uploadResult?.txHash;
    const uploadedRoot = typeof uploadResult === "object" && uploadResult?.rootHash
      ? uploadResult.rootHash
      : rootHash;
    if (!txHash) {
      throw new Error(`Upload completed without a transaction hash for root ${uploadedRoot}`);
    }

    return {
      root_hash: uploadedRoot,
      tx_hash: txHash,
      explorer_url: `${EXPLORER}/tx/${txHash || rootHash}`,
      storage_scan_url: `https://storagescan.0g.ai/file?cid=${uploadedRoot}`,
      indexer_url: INDEXER,
      rpc_url: EVM_RPC,
      flow_contract: FLOW_CONTRACT,
      market_contract: marketAddress,
      storage_fee_wei: fee.toString(),
      price_per_sector_wei: pricePerSector.toString(),
      chain_id: network.chainId.toString(),
    };
  } finally {
    await file.close();
  }
}

// CLI entrypoint
const [,, filePath, privateKey] = process.argv;
if (!filePath || !privateKey) {
  console.error("Usage: node upload.mjs <json_file> <private_key>");
  process.exit(1);
}

upload(path.resolve(filePath), privateKey)
  .then(result => {
    console.log(JSON.stringify(result));
  })
  .catch(err => {
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
  });
