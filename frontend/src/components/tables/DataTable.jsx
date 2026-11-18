import React, { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

export default function DataTable({
  columns,
  rows,
  emptyMessage = 'No records loaded from API yet.',
  loading = false,
  defaultSortKey = null,
  defaultSortDir = 'asc',
}) {
  const [sortKey, setSortKey] = useState(defaultSortKey);
  const [sortDir, setSortDir] = useState(defaultSortDir);

  function handleSort(col) {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(col.key);
      setSortDir('asc');
    }
  }

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    const activeCol = columns.find((c) => c.key === sortKey);
    if (!activeCol) return rows;

    return [...rows].sort((a, b) => {
      const valA = activeCol.sortValue ? activeCol.sortValue(a) : a[sortKey];
      const valB = activeCol.sortValue ? activeCol.sortValue(b) : b[sortKey];

      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDir === 'asc' ? valA - valB : valB - valA;
      }
      const cmp = String(valA).localeCompare(String(valB), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir, columns]);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((col) => {
                const isSorted = sortKey === col.key;
                return (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col)}
                    className={`px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 ${
                      col.sortable
                        ? 'cursor-pointer select-none hover:bg-slate-100 hover:text-slate-800'
                        : ''
                    } ${col.headerClassName || ''}`}
                  >
                    <div className="inline-flex items-center gap-1.5">
                      <span>{col.header}</span>
                      {col.sortable &&
                        (isSorted ? (
                          sortDir === 'asc' ? (
                            <ArrowUp className="h-3.5 w-3.5 text-teal-600" />
                          ) : (
                            <ArrowDown className="h-3.5 w-3.5 text-teal-600" />
                          )
                        ) : (
                          <ArrowUpDown className="h-3 w-3 text-slate-400" />
                        ))}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {loading ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-sm text-slate-500"
                >
                  Loading live data from MEDILOGIX API...
                </td>
              </tr>
            ) : sortedRows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-sm text-slate-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedRows.map((row, idx) => (
                <tr key={row.id || row.code || idx} className="hover:bg-slate-50/80">
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`whitespace-nowrap px-4 py-3 text-slate-700 ${
                        col.cellClassName || ''
                      }`}
                    >
                      {col.render ? col.render(row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
