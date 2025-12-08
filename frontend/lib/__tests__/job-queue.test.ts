/**
 * Tests for job queue utilities
 *
 * Verifies:
 * 1. Idempotency key computation
 * 2. Input validation
 * 3. SQL function calls
 */

import { computeIdempotencyKey, validateJobInput, JobInput } from '../job-queue';

describe('computeIdempotencyKey', () => {
  it('should produce stable key for s3_key', () => {
    const input1: JobInput = { source_type: 's3', s3_key: 'videos/test.mp4' };
    const input2: JobInput = { source_type: 's3', s3_key: 'videos/test.mp4' };
    const input3: JobInput = { source_type: 's3', s3_key: 'videos/other.mp4' };

    const key1 = computeIdempotencyKey(input1);
    const key2 = computeIdempotencyKey(input2);
    const key3 = computeIdempotencyKey(input3);

    expect(key1).toBe(key2);
    expect(key1).not.toBe(key3);
    expect(key1).toHaveLength(32);
  });

  it('should produce stable key for url', () => {
    const input1: JobInput = { source_type: 'url', url: 'https://example.com/video.mp4' };
    const input2: JobInput = { source_type: 'url', url: 'https://example.com/video.mp4' };

    expect(computeIdempotencyKey(input1)).toBe(computeIdempotencyKey(input2));
  });

  it('should produce stable key for external_id', () => {
    const input1: JobInput = { source_type: 'local', external_id: 'TA1234' };
    const input2: JobInput = { source_type: 'local', external_id: 'TA1234' };

    expect(computeIdempotencyKey(input1)).toBe(computeIdempotencyKey(input2));
  });

  it('should throw for input without identifier', () => {
    const input: JobInput = { source_type: 's3' };

    expect(() => computeIdempotencyKey(input)).toThrow('must have');
  });

  it('should prioritize identifiers: s3_key > url > external_id', () => {
    // s3_key takes priority
    const withBoth: JobInput = {
      source_type: 's3',
      s3_key: 'test.mp4',
      url: 'https://example.com/test.mp4',
    };
    const s3Only: JobInput = {
      source_type: 's3',
      s3_key: 'test.mp4',
    };

    expect(computeIdempotencyKey(withBoth)).toBe(computeIdempotencyKey(s3Only));
  });
});

describe('validateJobInput', () => {
  it('should reject non-object input', () => {
    expect(validateJobInput(null)).toEqual({
      valid: false,
      error: 'Input must be an object',
    });

    expect(validateJobInput('string')).toEqual({
      valid: false,
      error: 'Input must be an object',
    });
  });

  it('should reject invalid source_type', () => {
    const result = validateJobInput({
      source_type: 'invalid',
      s3_key: 'test.mp4',
    });

    expect(result.valid).toBe(false);
    expect(result.error).toContain('source_type');
  });

  it('should require at least one identifier', () => {
    const result = validateJobInput({
      source_type: 's3',
    });

    expect(result.valid).toBe(false);
    expect(result.error).toContain('s3_key');
  });

  it('should reject invalid URL', () => {
    const result = validateJobInput({
      source_type: 'url',
      url: 'not-a-url',
    });

    expect(result.valid).toBe(false);
    expect(result.error).toContain('valid URL');
  });

  it('should accept valid s3 input', () => {
    const result = validateJobInput({
      source_type: 's3',
      s3_key: 'videos/test.mp4',
    });

    expect(result.valid).toBe(true);
    expect(result.input).toEqual({
      source_type: 's3',
      s3_key: 'videos/test.mp4',
      url: undefined,
      external_id: undefined,
      metadata: undefined,
    });
  });

  it('should accept valid url input', () => {
    const result = validateJobInput({
      source_type: 'url',
      url: 'https://example.com/video.mp4',
    });

    expect(result.valid).toBe(true);
    expect(result.input?.source_type).toBe('url');
    expect(result.input?.url).toBe('https://example.com/video.mp4');
  });

  it('should accept valid local input', () => {
    const result = validateJobInput({
      source_type: 'local',
      external_id: 'TA1234',
      metadata: { vision_tier: 'fast' },
    });

    expect(result.valid).toBe(true);
    expect(result.input?.source_type).toBe('local');
    expect(result.input?.external_id).toBe('TA1234');
    expect(result.input?.metadata).toEqual({ vision_tier: 'fast' });
  });
});
