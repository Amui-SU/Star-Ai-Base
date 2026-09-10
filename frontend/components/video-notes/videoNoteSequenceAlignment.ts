export interface SequenceMatch {
  previousIndex: number;
  parsedIndex: number;
}

function collectUniqueIndexes(values: readonly string[]): Map<string, number> {
  const uniqueIndexes = new Map<string, number>();
  const duplicates = new Set<string>();

  values.forEach((value, index) => {
    if (duplicates.has(value)) {
      return;
    }

    if (uniqueIndexes.has(value)) {
      uniqueIndexes.delete(value);
      duplicates.add(value);
      return;
    }

    uniqueIndexes.set(value, index);
  });

  return uniqueIndexes;
}

export function alignUniqueFingerprints(
  previous: readonly string[],
  parsed: readonly string[],
): SequenceMatch[] {
  const previousUniqueIndexes = collectUniqueIndexes(previous);
  const parsedUniqueIndexes = collectUniqueIndexes(parsed);
  const pairs: SequenceMatch[] = [];

  for (const [fingerprint, previousIndex] of previousUniqueIndexes) {
    const parsedIndex = parsedUniqueIndexes.get(fingerprint);
    if (parsedIndex !== undefined) {
      pairs.push({ previousIndex, parsedIndex });
    }
  }

  pairs.sort((left, right) => left.previousIndex - right.previousIndex);

  const tails: number[] = [];
  const predecessors = new Array<number>(pairs.length).fill(-1);

  for (let pairIndex = 0; pairIndex < pairs.length; pairIndex += 1) {
    let low = 0;
    let high = tails.length;

    while (low < high) {
      const middle = low + Math.floor((high - low) / 2);
      if (pairs[tails[middle]].parsedIndex < pairs[pairIndex].parsedIndex) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }

    if (low > 0) {
      predecessors[pairIndex] = tails[low - 1];
    }
    tails[low] = pairIndex;
  }

  const matches: SequenceMatch[] = [];
  let pairIndex = tails.at(-1) ?? -1;
  while (pairIndex !== -1) {
    matches.push(pairs[pairIndex]);
    pairIndex = predecessors[pairIndex];
  }

  matches.reverse();
  return matches;
}
