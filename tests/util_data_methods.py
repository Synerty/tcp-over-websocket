import hashlib


def generateDeterministicData(sizeBytes: int, seed: int = 12345) -> bytes:
    """Generate deterministic data for testing with efficient chunking for large sizes"""
    if sizeBytes <= 1024 * 1024:  # 1MB or smaller - use simple approach
        data = bytearray(sizeBytes)
        for i in range(sizeBytes):
            data[i] = (seed + i) % 256
        return bytes(data)
    
    # For larger data, use chunking approach for better memory efficiency
    chunkSize = 1024 * 1024  # 1MB chunks
    data = bytearray(sizeBytes)

    for i in range(0, sizeBytes, chunkSize):
        endPos = min(i + chunkSize, sizeBytes)
        chunkLen = endPos - i

        # Generate chunk pattern more efficiently
        pattern = bytes((seed + i + j) % 256 for j in range(min(256, chunkLen)))
        patternLen = len(pattern)
        
        # Fill chunk by repeating pattern
        for j in range(0, chunkLen, patternLen):
            copyLen = min(patternLen, chunkLen - j)
            data[i + j:i + j + copyLen] = pattern[:copyLen]

    return bytes(data)


def calculateSha256(data: bytes) -> str:
    """Calculate SHA-256 checksum of data"""
    return hashlib.sha256(data).hexdigest()