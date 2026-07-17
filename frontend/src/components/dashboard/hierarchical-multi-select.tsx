import * as React from 'react'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

/**
 * Flat item shape. Items with no `parent` render as top-level rows. Items
 * whose `parent` matches another item's `value` are nested under that
 * parent and only shown once the parent is expanded. Items with a
 * `parent` that has no matching top-level item are grouped under a
 * synthetic parent labelled by their `parent` string (used for e.g.
 * "May 2026" month groups that aren't themselves selectable values).
 */
export interface HierarchicalItem {
  value: string
  label: string
  parent?: string
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
  isGroup: boolean
  value?: string
  children: HierarchicalItem[]
}

function buildTree(items: HierarchicalItem[]): { roots: TreeNode[]; leafValues: string[] } {
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

  const roots: TreeNode[] = []
  const seenGroups = new Set<string>()
  const leafValues: string[] = []

  topLevel.forEach((item) => {
    const children = childrenByParent.get(item.value)
    roots.push({
      key: item.value,
      label: item.label,
      isGroup: !!children?.length,
      value: item.value,
      children: children ?? [],
    })
    leafValues.push(item.value)
    children?.forEach((c) => leafValues.push(c.value))
  })

  // Parents referenced by children but with no matching top-level item
  // (synthetic group, e.g. month names that aren't real filter values).
  childrenByParent.forEach((children, parentKey) => {
    if (byValue.has(parentKey) || seenGroups.has(parentKey)) return
    seenGroups.add(parentKey)
    roots.push({ key: parentKey, label: parentKey, isGroup: true, children })
    children.forEach((c) => leafValues.push(c.value))
  })

  return { roots, leafValues }
}

/** Checkbox tri-state for a group/leaf node: true if fully selected,
 * 'indeterminate' if partially selected, false otherwise. */
function nodeCheckedState(node: TreeNode, selectedSet: Set<string>): boolean | 'indeterminate' {
  const groupValues = [...(node.value ? [node.value] : []), ...node.children.map((c) => c.value)]
  if (groupValues.length === 0) return false
  const selectedCount = groupValues.filter((v) => selectedSet.has(v)).length
  if (selectedCount === 0) return false
  if (selectedCount === groupValues.length) return true
  return 'indeterminate'
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

  const filteredRoots = React.useMemo(() => {
    if (!query.trim()) return roots
    const q = query.toLowerCase()
    return roots
      .map((root) => {
        const rootMatches = root.label.toLowerCase().includes(q)
        const matchingChildren = root.children.filter((c) => c.label.toLowerCase().includes(q))
        if (rootMatches) return root
        if (matchingChildren.length) return { ...root, children: matchingChildren }
        return null
      })
      .filter((r): r is TreeNode => r !== null)
  }, [roots, query])

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
    const groupValues = [...(node.value ? [node.value] : []), ...node.children.map((c) => c.value)]
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
          className={cn(
            'flex h-10 w-full items-center justify-between rounded-lg border border-border bg-background px-3 text-sm text-foreground shadow-sm transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50',
            className,
          )}
        >
          <span className={cn('truncate text-left', selected.length === 0 && 'text-muted-foreground')}>
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
            <div key={node.key}>
              <div className="flex items-center gap-1 px-2 py-1.5 hover:bg-muted/50">
                {node.children.length > 0 ? (
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
                  onCheckedChange={() =>
                    node.value && node.children.length === 0 ? toggleValue(node.value) : toggleGroup(node)
                  }
                />
                <label
                  htmlFor={`node-${node.key}`}
                  className="flex-1 cursor-pointer truncate text-sm"
                  onClick={(e) => {
                    e.preventDefault()
                    if (node.value && node.children.length === 0) toggleValue(node.value)
                    else toggleGroup(node)
                  }}
                >
                  {node.label}
                </label>
              </div>
              {expanded.has(node.key) &&
                node.children.map((child) => (
                  <div
                    key={child.value}
                    className="flex items-center gap-2 py-1.5 pl-9 pr-2 hover:bg-muted/50"
                  >
                    <Checkbox
                      id={`child-${child.value}`}
                      checked={selectedSet.has(child.value)}
                      onCheckedChange={() => toggleValue(child.value)}
                    />
                    <label
                      htmlFor={`child-${child.value}`}
                      className="flex-1 cursor-pointer truncate text-sm"
                    >
                      {child.label}
                    </label>
                  </div>
                ))}
            </div>
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
