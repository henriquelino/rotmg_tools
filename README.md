# rotmg_tools

some tools for realm of the mad god game

## How to update/create constants

Use [muledump render](https://github.com/BR-/muledump-render) to create the constants.js file

## How to use

Change accounts.json to use your accounts credentials, you can copy and paste your muledump accounts to accounts.json
Also, instead of using accounts.json you can pass email and password via arguments:
`python login.py --email="your_account_mail" --password="your_pass_here"`

## What dos it do?

* It's suposed to log into your accounts (count as daily login)
* Can dumps account infos so you can parse later (data like muledump does, like items in vault, pots, gifts, fame)
* Buy free packages that are available