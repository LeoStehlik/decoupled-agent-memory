import { redirect } from 'next/navigation'

export default function BrainReviewPage() {
  redirect('/brain?view=review')
}
