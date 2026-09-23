import { test, expect, navigate, read, screenshot } from './fixtures';
import { enterGuest } from './experience-helpers';

for (const language of ['en', 'es'] as const) {
  test(`${language}: empty guest maps a statement in owned currency and reviews duplicate intake`, async ({ page }) => {
    const en = language === 'en';
    await page.setViewportSize({ width: en ? 1440 : 390, height: 900 });
    await enterGuest(page, language, 'empty');
    await page.getByRole('button', { name: en ? 'Add an account' : 'Agregar una cuenta', exact: true }).click();
    await page.getByRole('button', { name: en ? 'Add account' : 'Agregar cuenta', exact: true }).first().click();
    const dialog = page.getByRole('dialog');
    const currency = en ? 'USD' : 'KWD';
    await dialog.getByLabel(en ? 'Name' : 'Nombre', { exact: true }).fill('Browser statement account');
    await dialog.getByLabel(en ? 'Institution' : 'Institución', { exact: true }).fill('Local records');
    await dialog.getByLabel(en ? 'Currency' : 'Moneda', { exact: true }).fill(currency);
    await dialog.getByLabel(en ? 'Opening balance' : 'Saldo inicial', { exact: true }).fill('1000');
    await dialog.getByRole('button', { name: en ? 'Save' : 'Guardar', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const account = (await read(page, '/accounts')).items[0];
    expect(account.currency).toBe(currency);
    const selected = await read(page, `/session?account_id=${account.id}`);
    expect(selected.currency_context).toMatchObject({ currency, source: 'selected_account', account_id: account.id });
    await page.goto(`/#accounts?account_id=${account.id}&record_id=${account.id}`);
    await expect(page.getByRole('combobox', { name: /Display currency, no conversion|Moneda, sin conversión/ })).toHaveValue(currency);
    await navigate(page, 'transactions');
    const separator = en ? ',' : '\t';
    const amount = en ? '-45.50' : '-45,125';
    const data = ['Booked'+separator+'Payee'+separator+'Value', ['18/09/2026','Browser café',amount].join(separator), ['19/09/2026','Browser café',amount].join(separator)].join('\n');
    async function reviewFile() {
      await page.getByRole('button', { name: en ? 'Import CSV' : 'Importar CSV', exact: true }).click();
      await dialog.getByRole('combobox', { name: en ? 'Account' : 'Cuenta', exact: true }).selectOption(account.id);
      await dialog.getByLabel(en ? 'CSV file' : 'Archivo CSV', { exact: true }).setInputFiles({ name: en ? 'statement.csv' : 'statement.tsv', mimeType: en ? 'text/csv' : 'text/tab-separated-values', buffer: Buffer.from(data) });
      await dialog.getByRole('button', { name: en ? 'Read columns' : 'Leer columnas', exact: true }).click();
      await dialog.getByRole('combobox', { name: en ? /^Date(?: Example:.*)?$/ : /^Fecha(?: Ejemplo:.*)?$/ }).selectOption('Booked');
      await dialog.getByRole('combobox', { name: en ? /^Merchant or purpose/ : /^Comercio o concepto/ }).selectOption('Payee');
      await dialog.getByRole('combobox', { name: en ? /^Amount(?: |$)/ : /^Importe(?: |$)/ }).selectOption('Value');
      await dialog.getByRole('combobox', { name: en ? 'Date format' : 'Formato de fecha', exact: true }).selectOption('DMY');
      await dialog.getByRole('combobox', { name: en ? /^Decimal separator/ : /^Separador decimal/ }).selectOption(en ? '.' : ',');
      await screenshot(page, `${language}-statement-mapping`);
      await dialog.getByRole('button', { name: en ? 'Prepare review' : 'Preparar revisión', exact: true }).click();
      await expect(dialog.locator('tbody tr')).toHaveCount(2);
      await expect(dialog).toContainText(currency);
    }
    await reviewFile();
    expect((await read(page, '/transactions')).total).toBe(0);
    const commit = dialog.getByRole('button', { name: en ? 'Save reviewed transactions' : 'Guardar movimientos revisados', exact: true });
    await commit.click();
    await expect(dialog.getByRole('status')).toContainText('2');
    await dialog.getByRole('button', { name: en ? 'Done' : 'Listo', exact: true }).click();
    expect((await read(page, '/transactions')).total).toBe(2);
    expect((await read(page, `/accounts/${account.id}`)).balance).toBe(en ? '909.00' : '909.750');
    await reviewFile();
    await expect(commit).toBeDisabled();
    await dialog.getByRole('button', { name: en ? 'Skip all similar transactions' : 'Omitir todos los similares', exact: true }).click();
    await expect(commit).toBeEnabled();
    await screenshot(page, `${language}-statement-duplicates`);
    await commit.click();
    await expect(dialog.getByRole('status')).toContainText('0');
    await dialog.getByRole('button', { name: en ? 'Done' : 'Listo', exact: true }).click();
    await page.reload();
    expect((await read(page, '/transactions')).total).toBe(2);
    expect((await read(page, `/accounts/${account.id}`)).balance).toBe(en ? '909.00' : '909.750');
  });
}
