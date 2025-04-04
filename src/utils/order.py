# order_utils.py
def get_new_order_idx(db_conn, table: str, parent_id: int, parent_col: str) -> float:
    """Get an order_idx for inserting after the last item in a group."""
    cursor = db_conn.cursor()
    cursor.execute(f"""
        SELECT MAX(order_idx) FROM {table}
        WHERE {parent_col} = ?
    """, (parent_id,))
    max_order = cursor.fetchone()[0]
    return (max_order or 0) + 1000  # Start at 1000, then 2000, 3000...


def rebalance_orders(db_conn, table: str, parent_id: int, parent_col: str):
    """Reset order_idx to multiples of 1000 to prevent floating-point creep."""
    cursor = db_conn.cursor()
    cursor.execute(f"""
        SELECT id FROM {table}
        WHERE {parent_col} = ?
        ORDER BY order_idx
    """, (parent_id,))
    items = cursor.fetchall()

    for idx, (item_id,) in enumerate(items, start=1):
        cursor.execute(f"""
            UPDATE {table} SET order_idx = ?
            WHERE id = ?
        """, (idx * 1000, item_id))

    db_conn.commit()
