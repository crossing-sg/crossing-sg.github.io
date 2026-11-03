"""Scientific local QA figures for the proposed submission network."""
import geopandas as gpd
import pandas as pd
from pathlib import Path
from production_policy import AUTO,REVIEW,NOT


def nus_map(output,result,rows,coverage):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig,ax=plt.subplots(figsize=(11,13),layout='constrained')
    colors={AUTO:'#00845c',REVIEW:'#d16a13',NOT:'#aab1b6'}
    candidates=gpd.GeoDataFrame(result['candidates'],geometry='geometry',crs=3414)
    for category in [NOT,REVIEW,AUTO]:
        data=candidates[candidates.category==category]
        if len(data):data.plot(ax=ax,color=colors[category],linewidth=.5 if category==NOT else 1.3,alpha=.45 if category==NOT else .9)
    existing=gpd.GeoDataFrame([r for r in rows if r['existing']],geometry='geometry',crs=3414)
    existing.plot(ax=ax,color='#244d70',linewidth=1.8)
    for name in ['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 4','Science Drive 4']:
        roads=candidates[candidates.osm_name.eq(name)]
        if len(roads):
            row=roads.loc[roads.length_m.idxmax()];point=row.geometry.interpolate(.5,normalized=True)
            ax.annotate(name,(point.x,point.y),xytext=(5,7),textcoords='offset points',fontsize=9,
                        bbox=dict(facecolor='white',edgecolor='none',alpha=.9))
    w,s,e,n=result['bundle']['mask'].bounds;ax.set_xlim(w,e);ax.set_ylim(s,n)
    ax.set_aspect('equal');ax.set_facecolor('#faf9f5');ax.ticklabel_format(useOffset=False,style='plain')
    ax.set_xlabel('SVY21 easting (m)');ax.set_ylabel('SVY21 northing (m)')
    ax.set_title('Final NUS validation: proposal-road coverage\nBlue: existing | Green: automatic | Orange: review | Grey: not automatic',fontsize=13)
    fig.legend(handles=[Line2D([0],[0],color=c,lw=2,label=n) for n,c in [('Existing website','#244d70'),('AUTO-ELIGIBLE','#00845c'),('REVIEW REQUIRED','#d16a13'),('NOT AUTOMATICALLY INCLUDED','#aab1b6')]],loc='outside lower center',ncol=2)
    fig.savefig(Path(output)/'NUS_FINAL_OVERVIEW.png',dpi=300);plt.close(fig)
