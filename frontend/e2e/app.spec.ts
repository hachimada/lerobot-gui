import { expect, test, type Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

/** The Hardware page as a user would have set it up (saved in the browser). */
async function withHardware(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('seeded')) return;
    sessionStorage.setItem('seeded', '1');
    const hardware = {
      followerPort: '/dev/ttyACM0',
      followerId: 'my_follower_arm',
      leaderPort: '/dev/ttyACM1',
      leaderId: 'my_leader_arm',
      cameras: [],
    };
    localStorage.setItem('lerobot-gui:v2', JSON.stringify({ page: 'rollout', values: { hardware }, openAdv: [] }));
  });
}

test('a command page writes only what was entered, runs it, streams its output and stops it', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#teleoperate');
  await expect(page.getByRole('heading', { name: 'Teleoperate' })).toBeVisible();
  const preview = page.locator('pre.preview');
  await expect(preview).toContainText('--robot.port=/dev/ttyACM0');
  await expect(preview).toContainText('--teleop.port=/dev/ttyACM1');
  await expect(preview).not.toContainText('--display_data');

  // a boolean: default, true or false; the value entered is written
  await page.getByLabel('Show in Rerun').selectOption('true');
  await expect(preview).toContainText('--display_data=true');
  await page.locator('summary', { hasText: 'Advanced' }).click();
  await page.getByLabel('Loop rate (Hz)').fill('30');
  await expect(preview).toContainText('--fps=30');
  // emptied again: back to lerobot's default, out of the command
  await page.getByLabel('Loop rate (Hz)').fill('');
  await expect(preview).not.toContainText('--fps');

  await page.getByRole('button', { name: 'Run', exact: true }).click();
  const out = page.locator('pre.term-out');
  // the process got the command as built (the fake prints its arguments)...
  await expect(out).toContainText('--teleop.id=my_leader_arm --display_data=true');
  await expect(page.getByText(/Running · /)).toBeVisible();
  // ...then redraws its table in place (cursor up), like lerobot: the output doesn't grow
  await expect(out).toContainText('NAME | NORM');
  const lines = (await out.textContent())!.split('\n').length;
  await page.waitForTimeout(500);
  expect((await out.textContent())!.split('\n').length).toBe(lines);

  await page.getByRole('button', { name: 'Stop' }).click();
  await expect(page.getByText(/^Stopped/)).toBeVisible();
  await expect(out).toContainText('stopped');
});

test('missing hardware blocks Run and says where to set it', async ({ page }) => {
  await page.goto('/#teleoperate');
  await expect(page.getByText('Set the follower port.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Open Hardware' }).first().click();
  await expect(page.getByRole('heading', { name: 'Hardware' })).toBeVisible();
});

test('malformed input blocks Run until it is fixed', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#rollout');
  await page.locator('summary', { hasText: 'Advanced' }).last().click();
  await page.getByLabel('Rename map').fill('not json');
  await expect(page.getByText(/Rename map: must be a JSON object/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeDisabled();
  await page.getByLabel('Rename map').fill('{"observation.images.front": "observation.images.top"}');
  await expect(page.locator('pre.preview')).toContainText('--rename_map=');
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeEnabled();
});

test('Find port: unplug, Enter, assign', async ({ page }) => {
  await page.goto('/#hardware');
  const card = page.locator('#findport-card');
  await card.getByRole('button', { name: 'Find port' }).click();
  await expect(card.getByText('Unplug the USB cable of one arm (only one).')).toBeVisible();
  await card.getByRole('button', { name: 'Enter' }).click();
  // the fake reports /dev/ttyACM1
  await expect(card.getByText('/dev/ttyACM1', { exact: true })).toBeVisible();
  // the board's serial, as the server read it from sysfs
  await expect(card.getByText(/^Board 5A00000002\b/)).toBeVisible();
  await card.getByRole('button', { name: 'Use as follower' }).click();
  await expect(page.getByRole('status')).toHaveText('follower → /dev/ttyACM1');
  await expect(card.getByRole('button', { name: 'follower ✓' })).toBeDisabled();
  await expect(page.getByLabel('Port').first()).toHaveValue('/dev/ttyACM1');
});

test('Plugged in now: confirm a board, swap the arms, choose a port with its board', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#hardware');
  const card = page.locator('#arms-card');
  const row = (tty: string) => card.locator('tr', { has: page.getByText(tty, { exact: true }) });
  // confirming remembers the board on the follower's port
  await row('/dev/ttyACM0').getByRole('button', { name: 'Confirm follower' }).click();
  await expect(page.getByText('Follower on /dev/ttyACM0 (board 5A00000001).')).toBeVisible();
  // the leader onto the follower's port: they swap, each with the board on its new port
  await row('/dev/ttyACM0').getByRole('button', { name: 'Leader', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Swapped: leader ↔ follower');
  await expect(page.getByText('Follower on /dev/ttyACM1 (board 5A00000002).')).toBeVisible();
  await expect(page.getByText('Leader on /dev/ttyACM0 (board 5A00000001).')).toBeVisible();
  // a port chosen in its field comes with its board; one without a board serial has none
  await card.getByLabel('Port').first().selectOption('/dev/ttyUSB0');
  await expect(page.getByText(/^Follower on \/dev\/ttyUSB0, board not recorded yet/)).toBeVisible();
  await card.getByLabel('Port').first().selectOption('/dev/ttyACM1');
  await expect(page.getByText('Follower on /dev/ttyACM1 (board 5A00000002).')).toBeVisible();
});

test('Check arms: the boards of the arms on the right port are remembered', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#hardware');
  await expect(page.getByText(/^Follower on \/dev\/ttyACM0, board not recorded yet/)).toBeVisible();
  const card = page.locator('#arms-card');
  await card.getByRole('button', { name: 'Check arms' }).click();
  // the fake machine's arms check out
  await expect(page.getByRole('status')).toHaveText('Remembered the board of the follower and leader');
  await expect(page.getByText('Follower on /dev/ttyACM0 (board 5A00000001).')).toBeVisible();
  await expect(page.getByText('Leader on /dev/ttyACM1 (board 5A00000002).')).toBeVisible();
  // remembering a board moves no arm: the result stays
  await expect(card.getByText(/^Checked at/)).toBeVisible();
});

test('lerobot’s choices fill the selects; values survive a reload', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#train');
  await page.getByLabel('Start from').getByRole('button', { name: 'New policy' }).click();
  // the policy types come from the installed lerobot (the first listing takes a few seconds)
  const type = page.getByLabel('Policy type');
  await expect(type.locator('option', { hasText: /^act$/ })).toHaveCount(1, { timeout: 60_000 });
  await type.selectOption('act');
  await expect(page.locator('pre.preview')).toContainText('--policy.type=act');
  await page.reload();
  await expect(page.locator('pre.preview')).toContainText('--policy.type=act');
});

test('a pretrained policy is picked from the Hub or a local checkpoint, with search', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#train');
  await page.getByLabel('Start from').getByRole('button', { name: 'Pretrained' }).click();
  await page.getByRole('button', { name: 'Hugging Face Hub' }).click();
  await page.getByLabel('Search models on the Hub').fill('fast');
  await page.getByRole('option', { name: /lerobot\/pi0fast-base/ }).click();
  await expect(page.locator('pre.preview')).toContainText('--policy.path=lerobot/pi0fast-base');

  await page.getByRole('button', { name: /^Local checkpoints/ }).click();
  await page.getByLabel('Search local checkpoints').fill('last');
  await page.getByRole('option', { name: /last \(step 50,000\)/ }).click();
  await expect(page.locator('pre.preview')).toContainText('checkpoints/last/pretrained_model');
});

test('Services: the made-up account, local data with delete and the Hub', async ({ page }) => {
  // the server's account and listings are made up: never this machine's credentials, caches or the network
  await page.goto('/#hardware');
  await page.getByRole('button', { name: 'Hugging Face' }).click();
  await expect(page.getByText('Logged in as')).toContainText('alice');
  await expect(page.getByText('alice/pick_place_20260105_093000', { exact: true })).toBeVisible();
  await expect(page.getByText('lerobot/pusht', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'lab/pick-demo' })).toBeVisible();
  page.once('dialog', (d) => void d.accept());
  await page.getByRole('button', { name: 'Delete lerobot/smolvla_base (model) from HF_HUB_CACHE' }).click();
  await expect(page.getByRole('status')).toContainText('Deleted `lerobot/smolvla_base`');
  await expect(page.getByText('lerobot/smolvla_base', { exact: true })).toHaveCount(0);
});

test('Train logs to Trackio, with the Spaces of earlier runs offered', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#train');
  await page.getByLabel('Trackio', { exact: true }).selectOption('true');
  const space = page.locator('.field', { has: page.getByLabel('Trackio Space', { exact: true }) });
  await space.getByRole('button', { name: 'alice/trackio' }).click();
  await expect(page.locator('pre.preview')).toContainText('--trackio.enable=true');
  await expect(page.locator('pre.preview')).toContainText('--trackio.space_id=alice/trackio');
  await expect(page.getByText('needs a Hugging Face login')).toHaveCount(0); // the made-up account is logged in
});

test('Trackio: reached from Train, runs the dashboard of a project and links its address', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#train');
  await page.getByRole('link', { name: 'Trackio', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Trackio' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'alice/trackio' })).toHaveAttribute('href', 'https://huggingface.co/spaces/alice/trackio');
  await page.getByRole('button', { name: 'pick-demo' }).click();
  await expect(page.locator('pre.preview')).toContainText('--project=pick-demo');
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  const out = page.locator('pre.term-out');
  await expect(out).toContainText('args show --project=pick-demo');
  const address = out.getByRole('link', { name: 'http://127.0.0.1:7860/?project=pick-demo' });
  await expect(address).toHaveAttribute('target', '_blank');
  await page.getByRole('button', { name: 'Stop' }).click();
  await expect(out).toContainText('closed');
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeEnabled();
});

test('Environment shows lerobot’s data dirs as lerobot resolves them', async ({ page }) => {
  await page.goto('/#hardware');
  await page.getByRole('button', { name: 'Environment' }).click();
  await expect(page.getByRole('heading', { name: 'Environment' })).toBeVisible();
  // the browser tests' server sets HF_LEROBOT_HOME for its fake workspace
  const home = page.locator('.env-row', { hasText: 'HF_LEROBOT_HOME' }).first();
  await expect(home.getByText('set in the environment')).toBeVisible();
  await expect(home.getByText('from lerobot.utils.constants')).toBeVisible();
  await expect(page.locator('.env-row', { hasText: 'HF_LEROBOT_CALIBRATION' }).getByText('default')).toBeVisible();
});

test('the theme: the system’s, or light / dark kept across a reload', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/#hardware');
  const html = page.locator('html');
  await expect(html).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Theme: Dark' }).click();
  await expect(html).toHaveAttribute('data-theme', 'dark');
  const dark = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(dark).toBe('rgb(11, 15, 25)'); // #0b0f19
  await page.reload();
  await expect(html).toHaveAttribute('data-theme', 'dark'); // set before the first paint
  await page.getByRole('button', { name: 'Theme: Auto (system)' }).click();
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(html).toHaveAttribute('data-theme', 'dark'); // auto follows the system
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(html).toHaveAttribute('data-theme', 'light');
});

test('a preset saves a page’s values and loads them back in their place', async ({ page }) => {
  await page.goto('/#teleoperate');
  const rerun = page.getByLabel('Show in Rerun');
  await rerun.selectOption('true');
  await page.getByRole('button', { name: 'Save as…' }).click();
  await page.getByRole('textbox', { name: 'Preset name' }).fill('with rerun');
  await page.getByRole('textbox', { name: 'Preset name' }).press('Enter');
  await expect(page.getByText('From with rerun')).toBeVisible();
  const command = page.locator('.preview');
  await expect(command).toContainText('--display_data=true');

  await rerun.selectOption('');
  await expect(page.getByText('changed', { exact: true })).toBeVisible();
  await expect(command).not.toContainText('--display_data');
  page.once('dialog', (d) => void d.accept());
  await page.getByRole('combobox', { name: 'Load a preset' }).selectOption('with rerun');
  await expect(rerun).toHaveValue('true');
  await expect(command).toContainText('--display_data=true');
  await expect(page.getByText('changed', { exact: true })).toHaveCount(0);
});

test('cameras: the ones checked on their frame are used, by the name given', async ({ page }) => {
  await withHardware(page);
  await page.goto('/#hardware');
  await page.locator('#cameras-card').getByRole('button', { name: 'Find cameras' }).click();
  // the fake saves a frame of /dev/video0 and /dev/video2
  const use = page.getByRole('checkbox', { name: 'Use /dev/video0' });
  await expect(use).not.toBeChecked();
  await expect(page.getByRole('checkbox', { name: 'Use /dev/video2' })).toBeVisible();
  await use.check();
  await page.goto('/#teleoperate');
  await expect(page.getByText(/The camera on .*\/dev\/video0.*: give it a name/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeDisabled();

  await page.goto('/#hardware');
  await page.getByLabel('Name of /dev/video0').fill('top');
  await page.getByLabel('Name of /dev/video0').press('Enter');
  await page.getByLabel('fps of /dev/video0').fill('30');
  await page.goto('/#teleoperate');
  const preview = page.locator('pre.preview');
  await expect(preview).toContainText('--robot.cameras="{top: {type: opencv, fps: 30, index_or_path: /dev/video0}}"');
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeEnabled();

  // unchecked: the name cleared, the settings kept, left out of the command
  await page.goto('/#hardware');
  await page.getByRole('checkbox', { name: 'Use /dev/video0' }).uncheck();
  await expect(page.getByLabel('Name of /dev/video0')).toHaveValue('');
  await expect(page.getByLabel('fps of /dev/video0')).toHaveValue('30');
  await page.goto('/#teleoperate');
  await expect(page.getByText(/No cameras used yet/)).toBeVisible();
  await expect(preview).not.toContainText('--robot.cameras');
});
