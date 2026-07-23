import * as React from 'react'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { filterTriggerClasses } from '@/components/dashboard/filter-control'

/**
 * Flat item shape describing a node in an arbitrarily-nested tree.
 *
 * - `value` is the unique key of the node AND — when the node is a leaf
 *   (`isGroup !== true`) — the filter value emitted upstream when the
 *   node is selected.
 * - `parent` references the `value` of another item to nest under. Chains
 *   are allowed (Year -> Month -> Week -> ...): `buildTree` recurses.
 * - `isGroup: true` marks a node as a hierarchy-only category (Year,
 *   Month, ...). Its `value` is NOT included in the selection set that
 *   `onChange` emits — only its descendant leaves are. Selecting a group
 *   toggles all descendant leaves via tri-state.
 * - Items whose `parent` doesn't reference any item's `value` are kept
 *   as synthetic parents labelled by their `parent` string, matching the
 *   pre-recursion behavior. Prefer explicit `isGroup: true` items in new
 *   code — the synthetic-parent path stays only for backward compat.
 */
export interface HierarchicalItem {
  value: string
  label: string
  parent?: string
  isGroup?: boolean
}

interface HierarchicalMultiSelectProps {
  items: HierarchicalItem[]
  selected: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  /** Show a text filter box at the bottom of the panel (matches the
   * reference "Holding" dropdown, which has a search input under the list). */
  searchable?: boolean
  disabled?: boolean
  className?: string
}

interface TreeNode {
  key: string
  label: string
  /** True for hierarchy-only nodes (Year/Month/...): their `value` is
   * excluded from the filter selection set; only descendant leaves are
   * emitted. Non-group nodes with children are still selectable leaves
   * in their own right AND act as group toggles for their children,
   * matching the pre-recursion 2-level Region/Market behavior. */
  isGroup: boolean
  /** Only set on selectable (non-group) nodes. */
  value?: string
  children: TreeNode[]
}

interface BuiltTree {
  roots: TreeNode[]
  /** Every leaf value in the tree (excludes synthetic-group values), used
   * for "Select all" and for computing tri-state on group toggles. */
  leafValues: string[]
}

function buildTree(items: HierarchicalItem[]): BuiltTree {
  const byValue = new Map(items.map((i) => [i.value, i]))
  const childrenByParent = new Map<string, HierarchicalItem[]>()
  const topLevel: HierarchicalItem[] = []

  items.forEach((item) => {
    if (item.parent) {
      const list = childrenByParent.get(item.parent) ?? []
      list.push(item)
      childrenByParent.set(item.parent, list)
    } else {
      topLevel.push(item)
    }
  })

  const leafValues: string[] = []

  function buildNode(item: HierarchicalItem): TreeNode {
    const rawChildren = childrenByParent.get(item.value) ?? []
    const children = rawChildren.map(buildNode)
    const isGroup = item.isGroup === true
    if (!isGroup) leafValues.push(item.value)
    return {
      key: item.value,
      label: item.label,
      isGroup,
      value: isGroup ? undefined : item.value,
      children,
    }
  }

  const roots: TreeNode[] = topLevel.map(buildNode)

  // Synthetic parents: `parent` strings that don't match any item's
  // `value`. Kept for backward compat with the pre-recursion 2-level shape
  // (e.g. month-name strings referenced as `parent` without a matching
  // Month item existed in earlier callers).
  const seenSynthetic = new Set<string>()
  childrenByParent.forEach((rawChildren, parentKey) => {
    if (byValue.has(parentKey) || seenSynthetic.has(parentKey)) return
    seenSynthetic.add(parentKey)
    const children = rawChildren.map(buildNode)
    roots.push({
      key: parentKey,
      label: parentKey,
      isGroup: true,
      children,
    })
  })

  return { roots, leafValues }
}

/** All descendant leaf values under a node (excludes group nodes). Used by
 * group toggles and tri-state. */
function descendantLeafValues(node: TreeNode): string[] {
  const out: string[] = []
  const stack: TreeNode[] = [node]
  while (stack.length) {
    const n = stack.pop()!
    if (!n.isGroup && n.value) out.push(n.value)
    for (const c of n.children) stack.push(c)
  }
  return out
}

/** Checkbox tri-state for any node — leaf or group — computed from
 * whichever of its own value (if selectable) plus every descendant leaf
 * is currently in `selectedSet`. */
function nodeCheckedState(node: TreeNode, selectedSet: Set<string>): boolean | 'indeterminate' {
  const values = descendantLeafValues(node)
  if (values.length === 0) return false
  const selectedCount = values.filter((v) => selectedSet.has(v)).length
  if (selectedCount === 0) return false
  if (selectedCount === values.length) return true
  return 'indeterminate'
}

interface NodeRowProps {
  node: TreeNode
  depth: number
  expanded: Set<string>
  toggleExpand: (key: string) => void
  selectedSet: Set<string>
  toggleValue: (value: string) => void
  toggleGroup: (node: TreeNode) => void
}

function NodeRow({
  node,
  depth,
  expanded,
  toggleExpand,
  selectedSet,
  toggleValue,
  toggleGroup,
}: NodeRowProps) {
  const hasChildren = node.children.length > 0
  const isLeaf = !hasChildren && !node.isGroup
  const onToggle = () => {
    if (isLeaf && node.value) toggleValue(node.value)
    else toggleGroup(node)
  }
  return (
    <div>
      <div
        className="flex items-center gap-1 py-1.5 pr-2 hover:bg-muted/50"
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => toggleExpand(node.key)}
            className="rounded p-0.5 text-muted-foreground hover:text-foreground"
            aria-label={expanded.has(node.key) ? 'Collapse' : 'Expand'}
          >
            {expanded.has(node.key) ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <Checkbox
          id={`node-${node.key}`}
          checked={nodeCheckedState(node, selectedSet)}
          onCheckedChange={onToggle}
        />
        <label
          htmlFor={`node-${node.key}`}
          className="flex-1 cursor-pointer truncate text-sm"
          onClick={(e) => {
            e.preventDefault()
            onToggle()
          }}
        >
          {node.label}
        </label>
      </div>
      {expanded.has(node.key) &&
        node.children.map((child) => (
          <NodeRow
            key={child.key}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            toggleExpand={toggleExpand}
            selectedSet={selectedSet}
            toggleValue={toggleValue}
            toggleGroup={toggleGroup}
          />
        ))}
    </div>
  )
}

/** Filter the tree by label match at any depth. A branch is kept if its
 * own label matches, OR any descendant's label matches (with non-matching
 * descendants pruned). */
function filterTree(nodes: TreeNode[], q: string): TreeNode[] {
  if (!q.trim()) return nodes
  const lower = q.toLowerCase()
  function walk(node: TreeNode): TreeNode | null {
    const selfMatches = node.label.toLowerCase().includes(lower)
    const filteredChildren = node.children.map(walk).filter((c): c is TreeNode => c !== null)
    if (selfMatches) return { ...node, children: filteredChildren.length ? filteredChildren : node.children }
    if (filteredChildren.length) return { ...node, children: filteredChildren }
    return null
  }
  return nodes.map(walk).filter((n): n is TreeNode => n !== null)
}

export function HierarchicalMultiSelect({
  items,
  selected,
  onChange,
  placeholder = 'All',
  searchable = false,
  disabled = false,
  className,
}: HierarchicalMultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set())
  const [query, setQuery] = React.useState('')

  const { roots, leafValues } = React.useMemo(() => buildTree(items), [items])

  const filteredRoots = React.useMemo(() => filterTree(roots, query), [roots, query])

  const selectedSet = React.useMemo(() => new Set(selected), [selected])
  const allSelected = leafValues.length > 0 && leafValues.every((v) => selectedSet.has(v))
  const someSelected = leafValues.some((v) => selectedSet.has(v))

  const toggleValue = (value: string) => {
    if (selectedSet.has(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  const toggleGroup = (node: TreeNode) => {
    const groupValues = descendantLeafValues(node)
    // Include the group's own value only if it's a real (non-group) leaf-
    // with-children — matches the pre-recursion Region/Market behavior
    // where ticking a Region also enables filtering on that Region as a
    // value in its own right.
    if (!node.isGroup && node.value && !groupValues.includes(node.value)) {
      groupValues.push(node.value)
    }
    if (groupValues.length === 0) return
    const allOn = groupValues.every((v) => selectedSet.has(v))
    if (allOn) {
      onChange(selected.filter((v) => !groupValues.includes(v)))
    } else {
      const merged = new Set(selected)
      groupValues.forEach((v) => merged.add(v))
      onChange(Array.from(merged))
    }
  }

  const toggleSelectAll = () => {
    onChange(allSelected ? [] : leafValues)
  }

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const summary = React.useMemo(() => {
    if (selected.length === 0) return placeholder
    if (allSelected) return 'All'
    if (selected.length === 1) {
      const match = items.find((i) => i.value === selected[0])
      return match?.label ?? selected[0]
    }
    return `${selected.length} selected`
  }, [selected, allSelected, items, placeholder])

  return (
    <Popover open={open} onOpenChange={disabled ? undefined : setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(filterTriggerClasses, className)}
        >
          <span className={cn('min-w-0 flex-1 truncate text-left', selected.length === 0 && 'text-muted-foreground')}>
            {summary}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[--radix-popover-trigger-width] min-w-[240px] max-w-[calc(100vw-2rem)] p-0"
      >
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <Checkbox
            checked={allSelected ? true : someSelected ? 'indeterminate' : false}
            onCheckedChange={toggleSelectAll}
            id="select-all"
          />
          <label htmlFor="select-all" className="cursor-pointer text-sm font-medium">
            Select all
          </label>
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {filteredRoots.length === 0 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">No options found</p>
          )}
          {filteredRoots.map((node) => (
            <NodeRow
              key={node.key}
              node={node}
              depth={0}
              expanded={expanded}
              toggleExpand={toggleExpand}
              selectedSet={selectedSet}
              toggleValue={toggleValue}
              toggleGroup={toggleGroup}
            />
          ))}
        </div>
        {searchable && (
          <div className="flex items-center gap-2 border-t border-border px-2 py-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="All"
              className="h-8 border-none px-1 shadow-none focus-visible:ring-0"
            />
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
