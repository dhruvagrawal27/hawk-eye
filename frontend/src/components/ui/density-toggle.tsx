import { Rows2, Rows3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useDensity } from '@/lib/density'

/**
 * Toggles compact ↔ comfortable row density for the whole console. Icon-only;
 * mount it in the top bar next to the other global controls.
 */
export function DensityToggle() {
  const [density, setDensity] = useDensity()
  const compact = density === 'compact'
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-8"
      aria-label={compact ? 'Switch to comfortable density' : 'Switch to compact density'}
      title={compact ? 'Comfortable rows' : 'Compact rows'}
      onClick={() => setDensity(compact ? 'comfortable' : 'compact')}
    >
      {compact ? <Rows3 className="size-4" /> : <Rows2 className="size-4" />}
    </Button>
  )
}
