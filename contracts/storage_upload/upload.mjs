/**
 * 0G Storage upload helper for XRPFi Verifiable Copilot.
 *
 * Usage:
 *   node upload.mjs <json_file> <private_key>
 *
 * Outputs JSON: { "root_hash": "0x...", "tx_hash": "0x...", "explorer_url": "..." }
 *
 * 0G Galileo Testnet endpoints (chain ID 80087)
 */

import { Indexer, ZgFile } from "@0glabs/0g-ts-sdk";
import { ethers } from "ethers";
import { createWriteStream, promises as fs } from "fs";
import path from "path";
import os from "os";

const EVM_RPC   = "https://evmrpc-testnet.0g.ai";
const INDEXER   = "https://indexer-storage-testnet-turbo.0g.ai";
const EXPLORER  = "https://chainscan-galileo.0g.ai";

async function upload(filePath, privateKey) {
  // Provider + signer
  const provider = new ethers.JsonRpcProvider(EVM_RPC);
  const signer = new ethers.Wallet(privateKey, provider);

  const balance = await provider.getBalance(signer.address);
  if (balance === 0n) {
    throw new Error(`No OG balance at ${signer.address} — get testnet tokens first`);
  }

  // Open file
  const file = await ZgFile.fromFilePath(filePath);
  const [tree, treeErr] = await file.merkleTree();
  if (treeErr) throw new Error(`Merkle tree error: ${treeErr}`);

  const rootHash = tree.rootHash();

  // Upload via indexer
  const indexer = new Indexer(INDEXER);
  const [txHash, uploadErr] = await indexer.upload(file, EVM_RPC, signer);
  if (uploadErr) throw new Error(`Upload error: ${uploadErr}`);

  await file.close();

  return {
    root_hash: rootHash,
    tx_hash: txHash || "0x" + rootHash.replace("0x", ""),
    explorer_url: `${EXPLORER}/tx/${txHash || rootHash}`,
    storage_scan_url: `https://storagescan-galileo.0g.ai/file?cid=${rootHash}`,
  };
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
