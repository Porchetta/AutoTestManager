import { ref } from "vue";

export function sortItems(items, sortKey, sortOrder) {
  const direction = sortOrder === "asc" ? 1 : -1;
  return [...items].sort((left, right) => {
    const leftValue = String(left?.[sortKey] ?? "");
    const rightValue = String(right?.[sortKey] ?? "");
    return (
      leftValue.localeCompare(rightValue, undefined, {
        numeric: true,
        sensitivity: "base",
      }) * direction
    );
  });
}

export function sortState(activeKey, activeOrder, key) {
  return {
    active: activeKey === key,
    ascending: activeKey === key && activeOrder === "asc",
    descending: activeKey === key && activeOrder === "desc",
  };
}

export function useSort(defaultKey) {
  const sortKey = ref(defaultKey);
  const sortOrder = ref("asc");

  function toggle(key) {
    if (sortKey.value === key) {
      sortOrder.value = sortOrder.value === "asc" ? "desc" : "asc";
      return;
    }
    sortKey.value = key;
    sortOrder.value = "asc";
  }

  function stateOf(key) {
    return sortState(sortKey.value, sortOrder.value, key);
  }

  return { sortKey, sortOrder, toggle, stateOf };
}
