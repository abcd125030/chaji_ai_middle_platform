'use client';

import React from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

export interface ColumnDef<TData> {
  header: string;
  accessor?: keyof TData;
  cell?: (row: TData) => React.ReactNode;
}

interface DataTableProps<TData> {
  columns: ColumnDef<TData>[];
  data: TData[];
  pageCount: number;
}

export function DataTable<TData>({
  columns,
  data,
  pageCount,
}: DataTableProps<TData>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = Number(searchParams.get('page')) || 1;

  const createPageURL = (pageNumber: number | string) => {
    const params = new URLSearchParams(searchParams);
    params.set('page', pageNumber.toString());
    return `${pathname}?${params.toString()}`;
  };

  return (
    <div className="space-y-4">
      <div
        className="rounded-md overflow-x-auto"
        style={{ border: '1px solid var(--border)' }}
      >
        <table className="w-full divide-y" style={{ borderColor: 'var(--border)' }}>
          <thead style={{ backgroundColor: 'var(--accent)' }}>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.header}
                  className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
                  style={{ color: 'var(--foreground)' }}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {data.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td
                    key={column.header}
                    className="px-6 py-4 text-sm"
                    style={{ color: 'var(--foreground)', opacity: 0.9 }}
                  >
                    {column.cell
                      ? column.cell(row)
                      : column.accessor
                      ? String(row[column.accessor])
                      : null}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <button
          onClick={() => router.push(createPageURL(page - 1))}
          disabled={page <= 1}
          className="rounded-md px-4 py-2 text-sm disabled:opacity-50"
          style={{
            border: '1px solid var(--border)',
            color: 'var(--foreground)',
          }}
        >
          Previous
        </button>
        <span className="text-sm" style={{ color: 'var(--foreground)' }}>
          Page {page} of {pageCount}
        </span>
        <button
          onClick={() => router.push(createPageURL(page + 1))}
          disabled={page >= pageCount}
          className="rounded-md px-4 py-2 text-sm disabled:opacity-50"
          style={{
            border: '1px solid var(--border)',
            color: 'var(--foreground)',
          }}
        >
          Next
        </button>
      </div>
    </div>
  );
}