""" In Wikipedia-20201016181627.xml there are pages downloaded at
https://en.wikipedia.org/wiki/Special:Export

Some of them are saved to Lists_of_*.wiki files.

The articles are:
List_of_modernist_composers
List_of_composers_of_African_descent
List_of_female_composers_by_birth_date
List_of_organ_composers
List_of_major_opera_composers
List_of_composers_for_the_classical_guitar
List_of_composers_and_their_preferred_lyricists
List_of_string_quartet_composers
List_of_20th-century_Mexican_composers
List_of_composers_influenced_by_the_Holocaust
List_of_ragtime_composers
List_of_Star_Trek_composers_and_music
List_of_Jewish_American_composers
List_of_female_composers_by_name
List_of_violinist/composers
List_of_composers_by_name
List_of_composers_for_lute
List_of_zarzuela_composers
List_of_operetta_composers
List_of_Classical-era_composers
List_of_television_theme_music_composers
List_of_English_Baroque_composers
List_of_English_Renaissance_composers
List_of_female_film_score_composers
List_of_film_score_composers
List_of_composers_of_Caribbean_descent
List_of_acousmatic-music_composers
List_of_Romantic-era_composers
Butterworth_Prize_for_Composition
List_of_postmodernist_composers
List_of_composers_of_musicals
List_of_postminimalist_composers
List_of_Doctor_Who_composers
List_of_minimalist_composers
List_of_composers_who_studied_law
Lists_of_composers
List_of_étude_composers
List_of_piano_composers
List_of_21st-century_classical_composers
List_of_Baroque_composers
List_of_symphony_composers
List_of_20th-century_classical_composers
List_of_Magnificat_composers
List_of_classical_music_composers_by_era
List_of_Songwriters_Hall_of_Fame_inductees
List_of_electroacoustic_composers_of_color
List_of_film_director_and_composer_collaborations
Category:Lists_of_composers_by_nationality
List_of_composers_for_lute_(nationality)
List_of_composers_for_lute_(chronological)
List_of_people_who_have_won_Academy,_Emmy,_Grammy,_and_Tony_Awards
List_of_Medieval_composers
List_of_Académie_des_Beaux-Arts_members:_Music
List_of_Carnatic_composers
List_of_Anglican_church_composers
List_of_Renaissance_composers
List_of_Spaghetti_Western_filmmakers
Chronological_lists_of_classical_composers
List_of_émigré_musicians_from_Nazi_Europe_who_settled_in_Britain
Dinesh_Subasinghe
List_of_Byzantine_composers
"""


import untangle

from fetch_wikipedia import lists

doc = untangle.parse('Wikipedia-20201016181627.xml')
for page in doc.mediawiki.page:
    title = page.title.cdata
    if title in lists:
        print(title)
        print(len(list(page.revision.text)))
        for text in page.revision.text:
            with open(title.replace(" ", "_"), "w") as f:
                f.write(text.cdata)

            # text.cdata
