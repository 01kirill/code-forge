const base = process.env.CODEFORGE_TEST_URL
if (!base) throw new Error('Set CODEFORGE_TEST_URL to an isolated fixture stack.')
const suffix = Date.now().toString(36)
const password = crypto.randomUUID()
async function request(path, { access, body, method, signal } = {}) {
  const response = await fetch(base + '/api' + path, {
    method,
    signal: signal ?? AbortSignal.timeout(15000),
    headers: {
      ...(body && { 'content-type': 'application/json' }),
      ...(access && { authorization: 'Bearer ' + access }),
    },
    body: body && JSON.stringify(body),
  })
  if (!response.ok) throw Error(path + ' ' + response.status)
  const text = await response.text()
  return text ? JSON.parse(text) : null
}
const users = []
for (let batch = 0; batch < 50; batch += 5) {
  users.push(
    ...(await Promise.all(
      Array.from({ length: 5 }, async (_, i) => {
        const name = 'load_' + suffix + '_' + (batch + i)
        const email = name + '@example.com'
        await request('/auth/register', { method: 'POST', body: { name, email, password } })
        const pair = await request('/auth/login', { method: 'POST', body: { email, password } })
        return pair.access_token
      }),
    )),
  )
}
const [owner] = users
const room = await request('/contest/contests', {
  method: 'POST',
  access: owner,
  body: { title: 'Прогон 50 пользователей', duration: 5, description: '' },
})
const endpoint = '/contest/contests/' + room.id
const task = (await request('/edu/contest-tasks', { access: owner })).find(
  (t) => t.title === 'Сумма двух чисел',
)
if (!task) throw new Error('Seed the demo task before measuring.')
await request(endpoint + '/problems', {
  method: 'PUT',
  access: owner,
  body: { task_ids: [task.task_id] },
})
await Promise.all(
  users
    .slice(1)
    .map((access) => request('/contest/join/' + room.invite, { method: 'POST', access })),
)
await request(endpoint + '/start', { method: 'POST', access: owner })
const participants = (await request(endpoint, { access: owner })).participants.length
if (participants !== users.length) throw new Error('The room is missing participants.')
console.log(JSON.stringify({ users: users.length, participants }))
const deadline = Date.now() + 15000
while ((await request(endpoint, { access: owner })).state === 'countdown') {
  if (Date.now() >= deadline) throw new Error('The contest did not start.')
  await new Promise((resolve) => setTimeout(resolve, 500))
}
const attempt = await request(endpoint + '/problems/A/submissions', {
  method: 'POST',
  access: owner,
  body: {
    language: 'python',
    code: 'print(sum(map(int, input().split())))',
  },
})
let verdict
for (let i = 0; i < 30; i++) {
  const state = await request(endpoint + '/submissions/' + attempt.id, { access: owner })
  verdict = state.result?.verdict
  if (verdict) break
  await new Promise((resolve) => setTimeout(resolve, 100))
}
if (verdict !== 'AC') throw new Error('The reference submission did not pass.')

const paths = [
  '/edu/courses',
  '/edu/courses/python-basics',
  '/edu/me/profile',
  endpoint + '/standings',
]
for (const path of paths) {
  const requests = () =>
    Promise.all(
      users.map(async (access) => {
        const start = performance.now()
        try {
          await request(path, { access, signal: AbortSignal.timeout(5000) })
          return { ms: performance.now() - start, ok: true }
        } catch {
          return { ms: performance.now() - start, ok: false }
        }
      }),
    )
  await requests()
  const samples = []
  for (let i = 0; i < 3; i++) samples.push(...(await requests()))
  samples.sort((a, b) => a.ms - b.ms)
  console.log(
    JSON.stringify({
      path,
      n: samples.length,
      errors: samples.filter((r) => !r.ok).length,
      ms: [samples[74], samples[142], samples[149]].map((r) => Math.round(r.ms * 100) / 100),
    }),
  )
}
