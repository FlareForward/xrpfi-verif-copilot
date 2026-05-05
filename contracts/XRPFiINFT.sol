// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title XRPFiINFT
 * @notice ERC-7857-compatible iNFT for XRPFi Verifiable Copilot.
 *
 * Each token represents a verifiable AI agent decision log:
 *   - encryptedURI: 0G storage reference for the DecisionRecord JSON
 *   - metadataHash: keccak256 of the canonical DecisionRecord payload
 *
 * Deployed on 0G Galileo Testnet (chainId 80087).
 * ETHGlobal Open Agents 2026 — FlareForward / Steven Hudspeth
 */
contract XRPFiINFT {
    // -----------------------------------------------------------------------
    // ERC-721 storage
    // -----------------------------------------------------------------------
    string public name = "XRPFi Verifiable Decision Log";
    string public symbol = "XRPFI";

    uint256 private _nextTokenId = 1;

    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
    mapping(uint256 => address) private _tokenApprovals;
    mapping(address => mapping(address => bool)) private _operatorApprovals;

    // -----------------------------------------------------------------------
    // ERC-7857 iNFT storage
    // -----------------------------------------------------------------------
    mapping(uint256 => string) private _encryptedURIs;
    mapping(uint256 => bytes32) private _metadataHashes;

    // -----------------------------------------------------------------------
    // Access control
    // -----------------------------------------------------------------------
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "XRPFiINFT: not owner");
        _;
    }

    // -----------------------------------------------------------------------
    // Events (ERC-721)
    // -----------------------------------------------------------------------
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Approval(address indexed owner, address indexed approved, uint256 indexed tokenId);
    event ApprovalForAll(address indexed owner, address indexed operator, bool approved);

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------
    constructor() {
        owner = msg.sender;
    }

    // -----------------------------------------------------------------------
    // ERC-7857 mint (matches INFTMinter ABI in src/integrations/zero_g/inft.py)
    // -----------------------------------------------------------------------
    /**
     * @notice Mint a new iNFT decision record.
     * @param to           Recipient address.
     * @param encryptedURI 0G storage URI / tx hash of the DecisionRecord JSON.
     * @param metadataHash keccak256 of the canonical DecisionRecord payload.
     * @return tokenId     The newly minted token ID.
     */
    function mint(
        address to,
        string calldata encryptedURI,
        bytes32 metadataHash
    ) external onlyOwner returns (uint256) {
        require(to != address(0), "XRPFiINFT: mint to zero address");

        uint256 tokenId = _nextTokenId++;
        _owners[tokenId] = to;
        _balances[to] += 1;
        _encryptedURIs[tokenId] = encryptedURI;
        _metadataHashes[tokenId] = metadataHash;

        emit Transfer(address(0), to, tokenId);
        return tokenId;
    }

    // -----------------------------------------------------------------------
    // ERC-721 view functions
    // -----------------------------------------------------------------------
    function tokenURI(uint256 tokenId) external view returns (string memory) {
        require(_owners[tokenId] != address(0), "XRPFiINFT: token does not exist");
        return _encryptedURIs[tokenId];
    }

    function metadataHash(uint256 tokenId) external view returns (bytes32) {
        require(_owners[tokenId] != address(0), "XRPFiINFT: token does not exist");
        return _metadataHashes[tokenId];
    }

    function ownerOf(uint256 tokenId) external view returns (address) {
        address tokenOwner = _owners[tokenId];
        require(tokenOwner != address(0), "XRPFiINFT: token does not exist");
        return tokenOwner;
    }

    function balanceOf(address addr) external view returns (uint256) {
        require(addr != address(0), "XRPFiINFT: zero address");
        return _balances[addr];
    }

    function totalSupply() external view returns (uint256) {
        return _nextTokenId - 1;
    }

    // -----------------------------------------------------------------------
    // ERC-721 approvals (minimal implementation)
    // -----------------------------------------------------------------------
    function approve(address to, uint256 tokenId) external {
        address tokenOwner = _owners[tokenId];
        require(msg.sender == tokenOwner, "XRPFiINFT: not token owner");
        _tokenApprovals[tokenId] = to;
        emit Approval(tokenOwner, to, tokenId);
    }

    function setApprovalForAll(address operator, bool approved) external {
        _operatorApprovals[msg.sender][operator] = approved;
        emit ApprovalForAll(msg.sender, operator, approved);
    }

    function getApproved(uint256 tokenId) external view returns (address) {
        return _tokenApprovals[tokenId];
    }

    function isApprovedForAll(address addr, address operator) external view returns (bool) {
        return _operatorApprovals[addr][operator];
    }

    function supportsInterface(bytes4 interfaceId) external pure returns (bool) {
        return
            interfaceId == 0x80ac58cd || // ERC-721
            interfaceId == 0x5b5e139f || // ERC-721Metadata
            interfaceId == 0x01ffc9a7;   // ERC-165
    }
}
