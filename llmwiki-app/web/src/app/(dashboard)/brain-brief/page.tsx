import { redirect } from 'next/navigation'

export default function BrainBriefPage() {
  redirect('/brain?view=brief')
}
