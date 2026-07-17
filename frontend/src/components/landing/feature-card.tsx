import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

interface FeatureCardProps {
  icon: LucideIcon
  title: string
  description: string
}

/**
 * Reusable feature/trust card for the landing page's capabilities grid.
 * Uses the app's semantic card tokens (bg-card / border-border / primary)
 * so it matches the dashboard's card style exactly, with a subtle
 * hover-lift + icon color inversion for premium feel.
 */
export function FeatureCard({ icon: Icon, title, description }: FeatureCardProps) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className="group h-full rounded-2xl border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-lg"
    >
      <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mb-1.5 text-base font-bold text-foreground">{title}</h3>
      <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
    </motion.div>
  )
}
