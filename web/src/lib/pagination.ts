/**
 * Standard offset-based pagination for list API endpoints.
 *
 * Usage:
 *   const { items, total, offset, hasMore } = paginate(allItems, url);
 */

const DEFAULT_PAGE_SIZE = 30;
const MAX_PAGE_SIZE = 100;

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  offset: number;
  hasMore: boolean;
}

export function paginate<T>(
  all: T[],
  url: URL,
  defaultLimit = DEFAULT_PAGE_SIZE,
): PaginatedResult<T> {
  const limit = Math.min(
    Math.max(Number(url.searchParams.get("limit") || defaultLimit), 1),
    MAX_PAGE_SIZE,
  );
  const offset = Math.max(Number(url.searchParams.get("offset") || 0), 0);

  const items = all.slice(offset, offset + limit);
  const hasMore = offset + limit < all.length;

  return { items, total: all.length, offset, hasMore };
}
