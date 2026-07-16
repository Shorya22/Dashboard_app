import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { Home, BarChart3, Users, GraduationCap, Table2, LogOut } from 'lucide-react'

import { Dialog, DialogContent } from '@/components/ui/dialog'
import { useAuth } from '@/lib/auth-context'
import { apiClient } from '@/lib/api-client'

export function CommandMenu({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const { setAuth } = useAuth()

  const run = (fn: () => void) => {
    onOpenChange(false)
    fn()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0">
        <Command className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-muted-foreground">
          <Command.Input
            placeholder="Type a command or search..."
            className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>
            <Command.Group heading="Navigation">
              {[
                { to: '/', label: 'Home', icon: Home },
                { to: '/hr-analytics', label: 'HR Analytics', icon: BarChart3 },
                { to: '/workforce', label: 'Workforce', icon: Users },
                { to: '/skills-experience', label: 'Skills & Experience', icon: GraduationCap },
                { to: '/employee-directory', label: 'Employee Directory', icon: Table2 },
              ].map((item) => (
                <Command.Item
                  key={item.to}
                  onSelect={() => run(() => navigate(item.to))}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground"
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Command.Item>
              ))}
            </Command.Group>
            <Command.Group heading="Account">
              <Command.Item
                onSelect={() =>
                  run(async () => {
                    try {
                      await apiClient.post('/auth/logout')
                    } finally {
                      setAuth(null)
                      navigate('/login', { replace: true })
                    }
                  })
                }
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground"
              >
                <LogOut className="h-4 w-4" />
                Log out
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  )
}
