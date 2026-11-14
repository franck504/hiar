"""
Catalogue des services HIAR : catégories -> éléments.

Source unique utilisée par l'interface (V0.9) et par la
construction des demandes structurées (V0.10).
"""

INFO_DISCLAIMER = (
    "Information générale non diagnostique. "
    "Elle ne remplace pas l'avis d'un professionnel de santé."
)


INFO_TEXTS = {
    'HIV': 'COMPRENDRE\nLe VIH (virus de l’immunodéficience humaine) attaque le système immunitaire. Le sida correspond au stade le plus avancé de l’infection. Avec un traitement antirétroviral adapté, une personne vivant avec le VIH peut vivre longtemps et en bonne santé.\n\nTRANSMISSION\nLe VIH peut être transmis par certains liquides biologiques : le sang, le sperme, les sécrétions vaginales et le lait maternel. Il peut également être transmis de la mère à l’enfant.\n\nCE QUI NE TRANSMET PAS LE VIH\nLe VIH ne se transmet pas par une poignée de main, une étreinte, un contact ordinaire, le partage d’un repas, d’eau ou de toilettes.\n\nSIGNES ET SYMPTÔMES POSSIBLES\nCertaines personnes ne présentent aucun symptôme. D’autres peuvent avoir, dans les premières semaines, de la fièvre, des maux de tête, une éruption cutanée ou un mal de gorge. Plus tard, une fatigue persistante, une perte de poids, de la fièvre ou des diarrhées peuvent apparaître. Ces signes ne permettent pas, à eux seuls, de confirmer une infection.\n\nPRÉVENTION ET PRÉCAUTIONS\n• Utiliser correctement un préservatif.\n• Ne jamais partager aiguilles, seringues ou matériel de soin susceptible d’être contaminé.\n• Demander conseil à un professionnel de santé concernant les moyens de prévention et le dépistage.\n• Éviter toute stigmatisation : le VIH ne se transmet pas par les contacts ordinaires.\n\nDÉPISTAGE ET PRISE EN CHARGE\nSeul un test de dépistage permet de connaître son statut VIH. En cas de résultat positif, un professionnel de santé accompagne la personne vers un traitement antirétroviral et un suivi régulier. Une charge virale durablement indétectable sous traitement empêche la transmission sexuelle du VIH.\n\nQUAND CONSULTER\nDemander un dépistage après une situation comportant un risque d’exposition ou en cas de doute. Après une exposition possible, contacter rapidement un service de santé pour connaître les mesures adaptées.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — VIH et sida, 15 juillet 2025.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/hiv-aids',
    'MALARIA': 'COMPRENDRE\nLe paludisme est une maladie provoquée par un parasite transmis principalement par la piqûre d’un moustique Anophèle femelle infecté. Il est présent dans les régions tropicales. Il ne se transmet pas par les contacts ordinaires entre personnes.\n\nTRANSMISSION\nLa transmission se fait essentiellement par la piqûre d’un moustique infecté. Plus rarement, elle peut survenir par du sang contaminé ou du matériel d’injection contaminé.\n\nSYMPTÔMES POSSIBLES\nLes premiers signes peuvent comprendre :\n• Fièvre.\n• Frissons et transpiration.\n• Maux de tête.\n• Fatigue et douleurs musculaires.\n\nFORMES GRAVES\nUne confusion, des convulsions ou des difficultés à respirer peuvent signaler une forme grave nécessitant une prise en charge médicale urgente.\n\nPRÉVENTION ET PRÉCAUTIONS\n• Dormir sous une moustiquaire imprégnée d’insecticide.\n• Porter des vêtements couvrants, surtout le soir.\n• Utiliser un répulsif adapté selon les recommandations.\n• Protéger les ouvertures avec des moustiquaires.\n• Demander conseil à un professionnel avant tout médicament préventif.\n\nDÉPISTAGE ET PRISE EN CHARGE\nLes symptômes ne suffisent pas à confirmer le paludisme. Un test rapide ou un examen prescrit par un professionnel est nécessaire. Le traitement doit être choisi par un professionnel de santé.\n\nQUAND CONSULTER\nEn cas de fièvre dans une zone où le paludisme circule, demander rapidement un test. Une confusion, des convulsions ou une difficulté à respirer nécessitent une prise en charge urgente. Les jeunes enfants et les femmes enceintes sont particulièrement exposés aux formes graves.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — Paludisme, 4 décembre 2025.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/malaria',
    'DIABETES': 'COMPRENDRE\nLe diabète est une maladie chronique caractérisée par un taux de glucose (sucre) trop élevé dans le sang. Cela peut être lié à une production insuffisante d’insuline ou à une mauvaise utilisation de cette hormone par l’organisme.\n\nSYMPTÔMES POSSIBLES\nLes signes peuvent être discrets, notamment dans le diabète de type 2 :\n• Soif intense.\n• Besoin d’uriner plus souvent.\n• Fatigue inhabituelle.\n• Vision floue.\n• Perte de poids inexpliquée.\n\nPRÉVENTION\nPour réduire le risque de diabète de type 2 :\n• Privilégier une alimentation variée et équilibrée.\n• Pratiquer régulièrement une activité physique adaptée.\n• Éviter le tabac.\n• Maintenir, dans la mesure du possible, un poids favorable à la santé.\n\nÀ RETENIR\nCes mesures ne permettent pas de prévenir tous les types de diabète. Le diabète de type 1, notamment, ne dispose pas actuellement d’un moyen de prévention connu.\n\nDÉPISTAGE ET PRISE EN CHARGE\nUne analyse de sang permettant de mesurer la glycémie est nécessaire au diagnostic. Le suivi, les médicaments éventuels et les objectifs de traitement sont déterminés par un professionnel de santé.\n\nPRÉCAUTIONS\nNe pas arrêter ou modifier seul un traitement prescrit. Un suivi régulier aide à prévenir les complications touchant notamment les yeux, les reins, le cœur et les nerfs.\n\nQUAND CONSULTER\nDemander un avis médical en cas de soif intense, d’urines fréquentes, de fatigue persistante ou de perte de poids inexpliquée. Un dépistage est nécessaire pour confirmer ou écarter le diabète.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — Diabète, 14 novembre 2024.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/diabetes',
    'HYPERTENSION': 'COMPRENDRE\nL’hypertension artérielle correspond à une pression trop élevée du sang dans les artères. Elle peut augmenter les risques de maladies cardiovasculaires et rénales lorsqu’elle n’est pas prise en charge.\n\nSYMPTÔMES POSSIBLES\nLa plupart des personnes hypertendues ne ressentent aucun symptôme. Une tension élevée peut donc passer inaperçue. Des maux de tête intenses, des troubles visuels, des vertiges ou des douleurs thoraciques peuvent survenir lorsque la pression est très élevée.\n\nDÉPISTAGE\nLa seule façon de savoir si sa tension est élevée est de la faire mesurer. Un professionnel de santé doit interpréter les résultats et, si nécessaire, répéter les mesures pour confirmer le diagnostic.\n\nPRÉVENTION\n• Réduire la consommation excessive de sel.\n• Manger davantage de fruits et de légumes.\n• Pratiquer une activité physique adaptée.\n• Éviter le tabac.\n• Respecter le suivi médical recommandé.\n\nPRÉCAUTIONS\nUne mesure isolée ne suffit pas toujours à établir un diagnostic. Ne pas interrompre ou modifier un traitement antihypertenseur sans avis médical.\n\nQUAND CONSULTER\nFaire contrôler régulièrement sa tension, même en l’absence de symptômes. Une douleur thoracique, une difficulté à respirer, une confusion ou un trouble soudain de la vision nécessitent une évaluation médicale urgente.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — Hypertension artérielle, 25 septembre 2025.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/hypertension',
    'TUBERCULOSIS': 'COMPRENDRE\nLa tuberculose est une maladie infectieuse causée par une bactérie. Elle touche le plus souvent les poumons, mais peut aussi atteindre d’autres organes. Elle peut être traitée et guérie avec une prise en charge adaptée.\n\nTRANSMISSION\nLa tuberculose pulmonaire se transmet par l’air lorsqu’une personne atteinte rejette des particules infectieuses en toussant, en éternuant ou en crachant.\n\nSYMPTÔMES POSSIBLES\n• Toux persistante, parfois accompagnée de sang.\n• Douleur dans la poitrine.\n• Fièvre.\n• Fatigue importante.\n• Perte de poids inexpliquée.\n• Sueurs nocturnes.\n\nPRÉVENTION ET PRÉCAUTIONS\n• Consulter en cas de toux persistante ou de symptômes évocateurs.\n• Aérer régulièrement les pièces.\n• Respecter les mesures de prévention indiquées par les professionnels de santé.\n• Effectuer un dépistage lorsqu’il est recommandé, notamment après un contact étroit avec une personne malade.\n• Le vaccin BCG protège notamment les jeunes enfants contre certaines formes graves.\n\nDÉPISTAGE ET PRISE EN CHARGE\nUn professionnel de santé peut demander des examens pour confirmer la maladie. Le traitement repose sur des médicaments spécifiques à prendre selon les prescriptions et pendant la durée prévue.\n\nQUAND CONSULTER\nConsulter rapidement en cas de toux persistante, de fièvre, de sueurs nocturnes ou de perte de poids inexpliquée, particulièrement après un contact avec une personne atteinte de tuberculose.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — Tuberculose, 24 mars 2026.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/tuberculosis',
    'MENSTRUAL_HEALTH': 'COMPRENDRE\nLes menstruations (règles) sont un processus naturel du cycle menstruel. La durée du cycle et l’expérience des règles varient d’une personne à l’autre.\n\nMANIFESTATIONS HABITUELLES\nCertaines personnes peuvent ressentir :\n• Des crampes ou douleurs dans le bas-ventre.\n• Des ballonnements.\n• Des maux de tête.\n• Des changements d’humeur.\n\nHYGIÈNE ET PRÉCAUTIONS\n• Se laver les mains avant et après le changement d’une protection.\n• Utiliser des protections menstruelles adaptées et propres.\n• Changer les protections selon leur type et les indications d’utilisation.\n• Nettoyer et sécher correctement les protections réutilisables.\n• Avoir accès à de l’eau, à des installations sanitaires et à un espace adapté.\n• Les menstruations ne sont ni une maladie ni une raison d’exclusion ou de honte.\n\nQUAND CONSULTER\nDemander un avis médical en cas de douleurs très fortes, de saignements abondants, de règles très irrégulières ou de symptômes qui perturbent les activités habituelles. Ces difficultés méritent d’être prises au sérieux.\n\nACCOMPAGNEMENT\nUn professionnel de santé peut aider à comprendre les changements du cycle et à rechercher une éventuelle cause lorsque les symptômes sont inhabituels ou gênants.\n\nSOURCE\nOrganisation mondiale de la Santé (OMS) — Santé menstruelle, 18 juin 2026.\nhttps://www.who.int/fr/news-room/fact-sheets/detail/menstrual-health',
}

CATALOG = {
    "CONSULTATION": {
        "label": "Consultation",
        "icon": "",
        "field": "action",
        "confirm": "Demande enregistrée : {label}.",
        "items": {
            "APPOINTMENT": {"label": "Prendre rendez-vous", "available": True},
            "VITAL_SIGNS": {"label": "Mesurer mes signes vitaux", "available": False},
        },
    },
    "ORIENTATION": {
        "label": "Orientation",
        "icon": "",
        "field": "destination",
        "confirm": "Je vous accompagne vers : {label}.",
        "items": {
            "PHARMACY": {"label": "Pharmacie", "icon": "", "available": True},
            "LABORATORY": {"label": "Laboratoire", "icon": "", "available": True},
            "RECEPTION": {"label": "Accueil / Réception", "icon": "", "available": True},
        },
    },
    "INFORMATION": {
        "label": "Renseignements",
        "icon": "ℹ",
        "field": "topic",
        "confirm": "Fiche d'information : {label}.",
        "items": {
            "HIV": {
                "label": "VIH / SIDA",
                "available": True,
                "info": INFO_TEXTS["HIV"],
            },
            "MALARIA": {
                "label": "Paludisme",
                "available": True,
                "info": INFO_TEXTS["MALARIA"],
            },
            "DIABETES": {
                "label": "Diabète",
                "available": True,
                "info": INFO_TEXTS["DIABETES"],
            },
            "HYPERTENSION": {
                "label": "Hypertension",
                "available": True,
                "info": INFO_TEXTS["HYPERTENSION"],
            },
            "TUBERCULOSIS": {
                "label": "Tuberculose",
                "available": True,
                "info": INFO_TEXTS["TUBERCULOSIS"],
            },
            "MENSTRUAL_HEALTH": {
                "label": "Menstruation et santé menstruelle",
                "available": True,
                "info": INFO_TEXTS["MENSTRUAL_HEALTH"],
            },
        },
    },
}
