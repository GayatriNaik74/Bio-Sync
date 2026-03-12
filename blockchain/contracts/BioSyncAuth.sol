// SPDX-License-Identifier: MIT
// BioSync Phase 3 — Authentication Audit Smart Contract
pragma solidity ^0.8.19;

contract BioSyncAuth {

    // ── Event structure stored on blockchain ──────────
    struct SecurityEvent {
        uint256 timestamp;     // when it happened
        string  sessionId;     // unique session identifier
        string  eventType;     // "ANOMALY", "LOCK", "RESTORE"
        uint8   trustScore;    // 0–100 at time of event
        string  riskLevel;     // "LOW", "MEDIUM", "HIGH"
        bool    sessionLocked; // true if session was locked
    }

    // ── Storage ───────────────────────────────────────
    SecurityEvent[] public events;
    mapping(string => bool) public lockedSessions;
    mapping(string => uint8) public sessionScores;
    address public owner;
    uint256 public totalEvents;

    // ── Blockchain events (emitted for Web3.py to listen) ─
    event AnomalyDetected(
        string sessionId,
        uint8  trustScore,
        string riskLevel,
        uint256 timestamp
    );
    event SessionLocked(
        string sessionId,
        uint256 timestamp
    );
    event SessionRestored(
        string sessionId,
        uint256 timestamp
    );

    // ── Constructor: called once on deploy ────────────
    constructor() {
        owner       = msg.sender;
        totalEvents = 0;
    }

    // ── Log a security event ──────────────────────────
    function logEvent(
        string memory sessionId,
        string memory eventType,
        uint8         trustScore,
        string memory riskLevel
    ) public {
        bool locked = (keccak256(bytes(eventType)) ==
                        keccak256(bytes("LOCK")));

        events.push(SecurityEvent({
            timestamp    : block.timestamp,
            sessionId    : sessionId,
            eventType    : eventType,
            trustScore   : trustScore,
            riskLevel    : riskLevel,
            sessionLocked: locked
        }));

        sessionScores[sessionId] = trustScore;
        totalEvents++;

        if (locked) {
            lockedSessions[sessionId] = true;
            emit SessionLocked(sessionId, block.timestamp);
        } else if (keccak256(bytes(eventType)) ==
                   keccak256(bytes("RESTORE"))) {
            lockedSessions[sessionId] = false;
            emit SessionRestored(sessionId, block.timestamp);
        } else {
            emit AnomalyDetected(sessionId, trustScore,
                                  riskLevel, block.timestamp);
        }
    }

    // ── Check if a session is locked ──────────────────
    function isLocked(string memory sessionId)
        public view returns (bool) {
        return lockedSessions[sessionId];
    }

    // ── Get latest trust score for a session ──────────
    function getScore(string memory sessionId)
        public view returns (uint8) {
        return sessionScores[sessionId];
    }

    // ── Get total number of events logged ─────────────
    function getEventCount() public view returns (uint256) {
        return totalEvents;
    }

    // ── Get a specific event by index ─────────────────
    function getEvent(uint256 index)
        public view returns (
            uint256, string memory, string memory,
            uint8, string memory, bool
        ) {
        SecurityEvent memory e = events[index];
        return (e.timestamp, e.sessionId, e.eventType,
                e.trustScore, e.riskLevel, e.sessionLocked);
    }
}