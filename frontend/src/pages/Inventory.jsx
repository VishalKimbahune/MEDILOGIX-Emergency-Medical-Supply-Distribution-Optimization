import React, { useEffect, useState } from 'react';
import PageHeader from '../components/common/PageHeader';
import DataTable from '../components/tables/DataTable';
import ModuleActionPlaceholder from '../components/forms/ModuleActionPlaceholder';
import { inventoryService } from '../services/inventoryService';
import { formatNumber } from '../utils/formatters';

export default function Inventory() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([inventoryService.list(), inventoryService.listProducts()])
      .then(([invRows, prodRows]) => {
        setItems(invRows);
        setProducts(prodRows);
      })
      .catch(() => {
        setItems([]);
        setProducts([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const prodById = Object.fromEntries(products.map((p) => [p.id, p]));

  const columns = [
    { key: 'inventory_code', header: 'Inventory ID' },
    { key: 'warehouse_id', header: 'Warehouse ID' },
    {
      key: 'product_id',
      header: 'Medical Product',
      render: (r) => prodById[r.product_id]?.name || `Product #${r.product_id}`,
    },
    {
      key: 'quantity_available',
      header: 'Available Stock',
      render: (r) => formatNumber(r.quantity_available),
    },
    {
      key: 'quantity_reserved',
      header: 'Reserved',
      render: (r) => formatNumber(r.quantity_reserved),
    },
    {
      key: 'reorder_level',
      header: 'Reorder Level',
      render: (r) => formatNumber(r.reorder_level),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Inventory & Medical Products"
        badge="Synthetic Stock"
        description="Warehouse-level stock availability across Oxygen Cylinders, IV Fluid Cartons, Trauma Kits, and Essential Medicine Boxes."
        actions={<ModuleActionPlaceholder label="+ Adjust Stock (Next Sprint)" />}
      />
      <DataTable
        columns={columns}
        rows={items}
        loading={loading}
        emptyMessage="No inventory records loaded from /api/inventory."
      />
    </div>
  );
}
