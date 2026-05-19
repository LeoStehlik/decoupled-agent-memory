import { redirect } from 'next/navigation'

export default function BrainHealthPage() {
  redirect('/brain?view=health')
}
